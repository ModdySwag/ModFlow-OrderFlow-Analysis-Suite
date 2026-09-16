"""
Control API — everything the GUI needs that the original dashboard never had:
read/write settings, start/stop the engine, capability discovery, log tailing
and a Telegram self-test.

Mounted at /api/control/* by the desktop launcher.
"""

from __future__ import annotations

import time

import asyncio
import datetime as dt
import json
import logging
import re
import os
import platform
import sys
import uuid
from typing import Any, Optional

from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Query

from orderflow_system.desktop import config_store, engine as engine_mod, logs
from orderflow_system.desktop import windows as windows_mod
from orderflow_system.desktop import deribit as deribit_mod

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/control", tags=["control"])


# ──────────────────────────────────────────────────────────────
# Boot / config
# ──────────────────────────────────────────────────────────────

@router.get("/bootstrap")
async def bootstrap() -> dict[str, Any]:
    """One call the GUI makes on load: config + capabilities + engine state."""
    cfg = config_store.load_config()
    return {
        "config": cfg,
        "status": engine_mod.engine.status(),
        "capabilities": engine_mod.capabilities(),
        "system": {
            "platform": sys.platform,
            "platform_name": platform.platform(),
            "python": platform.python_version(),
            "config_path": str(config_store.config_path()),
            "log_path": str(config_store.log_path()),
            "db_path": str(config_store.db_path()),
        },
    }


@router.get("/config")
async def get_config() -> dict[str, Any]:
    return config_store.load_config()


@router.post("/config")
async def put_config(cfg: dict = Body(...)) -> dict[str, Any]:
    """Patch settings (validated + clamped by the store).

    Patches, not replaces: the body is merged over the config already on disk, so a caller may post the
    one block it cares about without resetting everything else. Callers that compute an entire block and
    need a key inside it gone use their own endpoint (the layout operations do exactly that).
    """
    saved = config_store.merge_config(cfg)
    logs.install(saved.get("logging", {}).get("level", "INFO"))
    return {"ok": True, "config": saved, "config_path": str(config_store.config_path())}


@router.post("/config/reset")
async def reset_config() -> dict[str, Any]:
    return {"ok": True, "config": config_store.save_config(config_store.default_config())}


# ──────────────────────────────────────────────────────────────
# Capabilities
# ──────────────────────────────────────────────────────────────

@router.get("/capabilities")
async def capabilities(refresh: bool = Query(default=False)) -> dict[str, Any]:
    caps = engine_mod.capabilities()
    if refresh:
        symbols = [i["symbol"] for i in config_store.load_config()["instruments"]]
        caps["bybit_symbols"] = await asyncio.to_thread(engine_mod.bybit_validate, symbols)
        caps["binance_symbols"] = await asyncio.to_thread(engine_mod.binance_validate, symbols)
        caps["hyperliquid_symbols"] = await asyncio.to_thread(engine_mod.hyperliquid_validate, symbols)
        caps["okx_symbols"] = await asyncio.to_thread(engine_mod.okx_validate, symbols)
        caps["validated"] = True
    return caps


@router.get("/datasources")
async def datasources() -> dict[str, Any]:
    """Which instruments each feed can actually serve — the GUI greys out the rest."""
    cfg = config_store.load_config()
    symbols = [i["symbol"] for i in cfg["instruments"]]

    def has_mt5(sym: str) -> bool:
        spec = config_store.instrument_cfg(cfg, sym) or {}
        return bool(spec.get("mt5_symbol"))

    mt5 = engine_mod.mt5_status()
    return {
        "mt5": {
            "usable": mt5["available"],
            "reason": mt5["reason"] or "MetaTrader 5 bridge ready",
            "symbols": [s for s in symbols if has_mt5(s)] if mt5["available"] else [],
        },
        "bybit": {
            "usable": True,
            "reason": "Public Bybit perpetuals — crypto instruments only",
            "symbols": [s for s in symbols
                        if engine_mod.bybit_capable(config_store.instrument_cfg(cfg, s) or {"symbol": s})],
        },
        "binance": {
            "usable": True,
            "reason": "Public Binance USDⓈ-M futures — crypto perpetuals only",
            "symbols": [s for s in symbols
                        if engine_mod.binance_capable(config_store.instrument_cfg(cfg, s) or {"symbol": s})],
        },
        "hyperliquid": {
            "usable": True,
            "reason": "Public Hyperliquid perpetuals — crypto instruments only",
            "symbols": [s for s in symbols
                        if engine_mod.hyperliquid_capable(config_store.instrument_cfg(cfg, s) or {"symbol": s})],
        },
        "okx": {
            "usable": True,
            "reason": "Public OKX USDT swaps — crypto instruments only",
            "symbols": [s for s in symbols
                        if engine_mod.okx_capable(config_store.instrument_cfg(cfg, s) or {"symbol": s})],
        },
    }


# ──────────────────────────────────────────────────────────────
# Instrument catalogue (public venue data — no key, no account)
# ──────────────────────────────────────────────────────────────

#: Well-known linear perpetuals a fresh install can add in one click — derived from
#: the instrument matrix so a new major cannot be listed in one place and missing in
#: the other. MATICUSDT is here on purpose: Bybit delisted it in favour of POLUSDT,
#: and a returning user's old position should still resolve.
VENUE_MAJORS = [*config_store.BYBIT_FALLBACK_SYMBOLS, "MATICUSDT"]


def _fetch_venue_catalog() -> dict[str, dict[str, Any]]:
    """One public call returns every linear perpetual with its tick size."""
    import json
    import urllib.request

    url = "https://api.bybit.com/v5/market/instruments-info?category=linear&limit=1000"
    with urllib.request.urlopen(url, timeout=15) as resp:
        payload = json.loads(resp.read().decode())
    out: dict[str, dict[str, Any]] = {}
    for row in (payload.get("result", {}).get("list") or []):
        sym = str(row.get("symbol") or "")
        if not sym:
            continue
        out[sym] = {
            "symbol": sym,
            "tick_size": float((row.get("priceFilter") or {}).get("tickSize") or 0.1),
            "status": str(row.get("status") or ""),
        }
    return out


@router.get("/instruments/catalog")
async def instruments_catalog() -> dict[str, Any]:
    """Which well-known instruments the venue actually lists (public data)."""
    try:
        catalog = await asyncio.to_thread(_fetch_venue_catalog)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "majors": [], "venue_total": 0}
    cfg = config_store.load_config()
    have = {i["symbol"] for i in cfg.get("instruments", [])}
    majors = [
        {**catalog[s], "in_config": s in have}
        for s in VENUE_MAJORS if s in catalog and catalog[s]["status"] in ("Trading", "")
    ]
    return {"ok": True, "majors": majors, "venue_total": len(catalog)}


@router.post("/instruments/add")
async def instruments_add(payload: dict = Body(default={})) -> dict[str, Any]:
    """Add venue-listed instruments to the config, tick sizes straight from the venue.

    A fresh install ships one crypto instrument; this is how the setup assistant
    offers the rest without anyone hand-editing config files.
    """
    import json

    wanted = [str(s).upper().strip() for s in (payload.get("symbols") or []) if str(s).strip()]
    if not wanted:
        return {"ok": False, "error": "no symbols given", "added": [], "updated": []}
    try:
        catalog = await asyncio.to_thread(_fetch_venue_catalog)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "added": [], "updated": []}

    cfg = config_store.load_config()
    instruments = cfg.get("instruments") or []
    by_symbol = {i["symbol"]: i for i in instruments}
    template = by_symbol.get("BTCUSDT") or (instruments[0] if instruments else {})
    added: list[str] = []
    updated: list[str] = []

    for sym in wanted:
        info = catalog.get(sym)
        if info is None or info.get("status") not in ("Trading", ""):
            continue
        if sym in by_symbol:
            inst = by_symbol[sym]
            inst["bybit_symbol"] = sym
            inst["tick_size"] = info["tick_size"]
            updated.append(sym)
        else:
            inst = {
                "symbol": sym,
                "asset_class": "Crypto",
                "enabled": False,
                "mt5_symbol": "",
                "bybit_symbol": sym,
                "tick_size": info["tick_size"],
                "patterns": json.loads(json.dumps(template.get("patterns") or {})),
            }
            instruments.append(inst)
            by_symbol[sym] = inst
            added.append(sym)

    if payload.get("enable"):
        for sym in added + updated:
            by_symbol[sym]["enabled"] = True

    saved = config_store.save_config(cfg)
    return {"ok": True, "added": added, "updated": updated, "config": saved}


# ──────────────────────────────────────────────────────────────
# Options — Deribit's public chain (keyless, crypto only; desktop/deribit.py)
# ──────────────────────────────────────────────────────────────

@router.get("/deribit/chain")
async def deribit_chain(symbol: str = "", expiry: str = "", width: int = deribit_mod.DEFAULT_WIDTH) -> dict[str, Any]:
    """The option chain for one currency: every expiry, and a strike ladder with IV and the Greeks.

    Deribit is public and keyless, and the browser can never reach it (the venue sends no CORS
    header), so this route is the only door to it. Off the event loop: the ladder reads up to
    2*width+1 instruments at ~0.4 s each, cached for 5 s (tickers 3 s).
    """
    return await asyncio.to_thread(deribit_mod.chain, symbol, expiry, width)


@router.get("/deribit/ticker")
async def deribit_ticker(instrument: str = "") -> dict[str, Any]:
    """One contract's ticker: mark, IV, bid/ask, open interest, volume and the full Greek set."""
    return await asyncio.to_thread(deribit_mod.ticker, instrument)


# ──────────────────────────────────────────────────────────────
# Studies (indicator module for this suite's contracts)
# ──────────────────────────────────────────────────────────────

#: Where indicator modules live. Only this directory is listed, and only *.js files in
#: it: the server never reads outside it, so a request cannot walk the filesystem.
STUDY_MODULE_DIR = Path(__file__).resolve().parent / "ui" / "indicators"


@router.get("/studies/library")
async def studies_library() -> dict[str, Any]:
    """List indicator modules: shipped files plus modules saved through the Studies view.

    The browser loads and validates each module (the contract check lives in
    `desktop/ui/study-api.js`), so this endpoint only answers "what is there to load".
    """
    modules: list[str] = []
    try:
        if STUDY_MODULE_DIR.is_dir():
            for path in sorted(STUDY_MODULE_DIR.glob("*.js")):
                modules.append(f"/desktop/indicators/{path.name}")
    except OSError as exc:                                  # pragma: no cover - fs errors
        logger.warning("study library listing failed: %s", exc)
    cfg = config_store.load_config()
    studies = cfg.get("studies") or {}
    custom = [c for c in (studies.get("custom") or []) if isinstance(c, dict) and c.get("enabled", True)]
    return {"ok": True, "modules": modules, "custom": custom,
            "directory": str(STUDY_MODULE_DIR),
            "note": ("Modules are plain files in desktop/ui/indicators — drop one in and "
                     "reload the view. Everything runs in your own browser session.")}


def _study_name_from_source(source: str) -> str:
    """Best-effort name for a pasted module (the browser validates it properly)."""
    match = __import__("re").search(r"""name\s*:\s*['"]([A-Za-z][A-Za-z0-9_-]{1,40})['"]""", source)
    return match.group(1) if match else ""


@router.post("/studies")
async def studies_save(payload: dict = Body(default={})) -> dict[str, Any]:
    """Save the active studies, or add/replace a pasted module."""
    cfg = config_store.load_config()
    studies = cfg.setdefault("studies", {})
    if isinstance(payload.get("active"), list):
        studies["active"] = payload["active"]
    if payload.get("custom_source"):
        source = str(payload["custom_source"])[:20000]
        name = _study_name_from_source(source)
        if not name:
            return {"ok": False, "error": "the module needs a name field, e.g. name: 'myStudy'"}
        custom = [c for c in (studies.get("custom") or []) if isinstance(c, dict) and c.get("name") != name]
        custom.append({"name": name, "source": source, "enabled": True})
        studies["custom"] = custom
    if payload.get("remove_custom"):
        target = str(payload["remove_custom"])
        studies["custom"] = [c for c in (studies.get("custom") or [])
                             if not (isinstance(c, dict) and c.get("name") == target)]
    saved = config_store.save_config(cfg)
    return {"ok": True, "studies": saved.get("studies") or {},
            "note": "Stored in your config file; modules run in your browser session."}


# ──────────────────────────────────────────────────────────────
# Order-flow engine (footprint matrix + depth heatmap) parameters
# ──────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────
# Free data connections (public, keyless feeds only)
# ──────────────────────────────────────────────────────────────

# (id, name, hint, probe url, wired) — `wired` means THIS build's engine can stream it today.
# The rest are reachable and free, and are listed as detected-but-not-ingestible rather than
# offered as a switch that would silently fall back to bybit.
FREE_SOURCES = (
    ("bybit", "Bybit", "public WS + REST — trades, order book depth, candles, no key",
     "https://api.bybit.com/v5/market/time", True),
    ("binance", "Binance Futures", "public WS + REST — trades, 100–1000-level book, candles, no key",
     "https://fapi.binance.com/fapi/v1/time", True),
    ("mt5", "MetaTrader 5", "your local terminal — free if it is installed here", "", True),
    ("alpaca", "Alpaca crypto", "keyless crypto quotes and bars (no book)",
     "https://data.alpaca.markets/v1beta3/crypto/us/latest/quotes?symbols=BTC%2FUSD", True),
    ("okx", "OKX", "public WS + REST — trades, 400-level book, no key",
     "https://www.okx.com/api/v5/public/time", True),
    ("hyperliquid", "Hyperliquid", "public WS + REST — trades, whole-book snapshots, no key",
     "https://api.hyperliquid.xyz/info", True),
)

#: POST-only probe bodies: Hyperliquid's `/info` answers a bare GET with 405, so a plain GET probe
#: would paint the venue "unreachable" while it is healthy. The probe then sends what the adapter
#: itself sends (one `meta` call).
_PROBE_PAYLOADS = {"hyperliquid": {"type": "meta"}}


def _probe_source(url: str, timeout: float = 4.0, payload: Optional[dict] = None) -> str:
    """ok / unreachable / installed — a reachability fact, never a guess about capability.

    ``payload`` is for POST-only endpoints (see `_PROBE_PAYLOADS`): the probe then makes the same
    request the adapter makes, instead of a GET the venue answers with 405.
    """
    if not url:
        try:
            import importlib
            importlib.import_module("MetaTrader5")
            return "ok"
        except Exception:
            return "idle"
    try:
        import urllib.request
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"User-Agent": "OrderFlow-Analysis-Pro"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return "ok" if 200 <= getattr(resp, "status", 200) < 400 else "unreachable"
    except Exception:
        return "unreachable"


@router.get("/sources")
async def sources() -> dict[str, Any]:
    """Every data source that costs nothing, with a live reachability read and the active one."""
    cfg = config_store.load_config()
    active = str(cfg.get("data_source") or "bybit")
    rows = [
        {"id": sid, "name": name, "hint": hint,
         "status": _probe_source(url, payload=_PROBE_PAYLOADS.get(sid)), "wired": wired}
        for sid, name, hint, url, wired in FREE_SOURCES
    ]
    return {"ok": True, "sources": rows, "active": active,
            "note": "Only keyless/public feeds are listed; nothing here needs an account or a key."}


@router.post("/source")
async def set_source(payload: dict = Body(default={})) -> dict[str, Any]:
    """Switch the active source. Only sources this build can actually ingest are accepted."""
    wanted = str((payload or {}).get("source") or "").strip().lower()
    wired = {sid for sid, _n, _h, _u, ok in FREE_SOURCES if ok}
    allowed = wired | {"both", "all"}
    if wanted in {sid for sid, *_ in FREE_SOURCES} and wanted not in wired:
        return {"ok": False, "error": f"{wanted!r} is reachable but this build has no feed adapter for it",
                "switchable": sorted(allowed)}
    if wanted not in allowed:
        return {"ok": False, "error": f"unknown source {wanted!r}", "switchable": sorted(allowed)}
    cfg = config_store.load_config()
    cfg["data_source"] = wanted
    saved = config_store.save_config(cfg)

    # End-to-end: the engine is rebuilt against the new source now, not "next start". The
    # restart path is the same one the toolbar's Restart button uses, so there is one code path.
    applied = None
    try:
        if engine_mod.engine.state in ("running", "starting"):   # state is a property, not a method
            applied = await engine_mod.engine.restart(config_store.load_config())
    except Exception as exc:                                    # pragma: no cover - engine errors
        logger.warning("engine restart after source switch failed: %s", exc)
        applied = {"ok": False, "error": str(exc)}
    live = {}
    try:
        live = engine_mod.engine.live_status()
    except Exception:
        live = {}
    # Hoisted so the message builds on Python < 3.12 too: a nested same-quote f-string
    # (f"…{applied.get("error")}…") is PEP 701 syntax and would not even parse on 3.11.
    restart_error = applied.get("error", "unknown") if applied else "unknown"
    return {"ok": True, "data_source": saved.get("data_source"),
            "engine": applied or {"restarted": False, "reason": "engine was not running"},
            "live": live,
            "note": ("engine restarted on the new source" if (applied and applied.get("ok") is not False)
                     else ("source saved; press Start engine to stream it" if not applied
                           else f"source saved; the restart failed ({restart_error})"))}


# ──────────────────────────────────────────────────────────────
# Workspaces (named layouts; they live in the config file, not a browser)
# ──────────────────────────────────────────────────────────────




@router.post("/params")
async def params_set(payload: dict = Body(default={})) -> dict[str, Any]:
    """Set one registered display variable.

    Only paths the registry knows are accepted, the value is coerced to the registered kind, and
    `config_store.save_config` clamps it afterwards — so the UI can never write a variable the store
    would reject, and it adopts the value that comes back.
    """
    from orderflow_system.desktop import param_registry

    path = str(payload.get("path") or "")
    param = param_registry.BY_PATH.get(path)
    if param is None:
        return {"ok": False, "error": f"unknown variable: {path or '(none)'}"}
    raw = payload.get("value")
    try:
        if param.kind == "number":
            value: Any = float(raw)
        elif param.kind == "bool":
            value = bool(raw)
        elif param.kind == "enum":
            value = str(raw)
            if param.choices and value not in param.choices:
                return {"ok": False, "error": f"{value} is not one of {list(param.choices)}"}
        else:
            return {"ok": False, "error": f"{path} is a {param.kind} variable and is edited elsewhere"}
    except (TypeError, ValueError):
        return {"ok": False, "error": f"{raw!r} is not a valid {param.kind}"}

    cfg = config_store.load_config()
    node = cfg
    parts = path.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            return {"ok": False, "error": f"{path} does not resolve to a settings block"}
    node[parts[-1]] = value
    saved = config_store.save_config(cfg)
    found, applied = param_registry._walk(saved, path)
    return {"ok": True, "path": path, "value": applied if found else None,
            "default": param_registry.current(config_store.default_config(), param),
            "applies": param.applies,
            "note": "stored in your config file" + (" — needs an engine restart" if param.applies == "restart" else "")}


@router.post("/folder/open")
async def folder_open(payload: dict = Body(default={})) -> dict[str, Any]:
    """Open one of the app's own folders in the OS file browser (the reference platform's File > Open user folder).

    Whitelisted names only: this never takes a path from the caller.
    """
    import os
    import subprocess
    import sys as _sys

    which = str(payload.get("folder") or "config").strip().lower()
    targets = {
        "config": config_store.config_path().parent,
        "logs": config_store.log_path().parent,
        "exports": config_store.config_path().parent / "exports",
    }
    if which not in targets:
        return {"ok": False, "error": f"unknown folder: {which}", "known": sorted(targets)}
    target = targets[which]
    try:
        target.mkdir(parents=True, exist_ok=True)
        if _sys.platform.startswith("win"):
            os.startfile(str(target))            # type: ignore[attr-defined]
        elif _sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
    except Exception as exc:                     # a headless run has no file browser
        return {"ok": False, "error": str(exc), "path": str(target)}
    return {"ok": True, "folder": which, "path": str(target)}


@router.get("/drawings")
async def drawings_get(symbol: str = "", view: str = "") -> dict[str, Any]:
    """The stored drawings for one view+symbol slot (they live in the config, in data space)."""
    cfg = config_store.load_config()
    key = f"{view or 'chart'}:{(symbol or '').upper()}"
    return {"ok": True, "key": key, "block": (cfg.get("drawings") or {}).get(key) or {}}


@router.post("/drawings")
async def drawings_post(payload: dict = Body(default={})) -> dict[str, Any]:
    """Store the drawings for one view+symbol slot.

    The block is sanitised by `config_store` (kinds whitelisted, points finite, colours restricted to
    hex/rgba, counts capped), and the stored block is returned so the UI adopts exactly what the
    store accepted instead of what it hoped it sent.
    """
    cfg = config_store.load_config()
    key = f"{str(payload.get('view') or 'chart')[:24]}:{str(payload.get('symbol') or '').upper()[:24]}"
    spaces = cfg.setdefault("drawings", {})
    if not isinstance(spaces, dict):
        spaces = {}
        cfg["drawings"] = spaces
    spaces[key] = payload
    saved = config_store.save_config(cfg)
    block = (saved.get("drawings") or {}).get(key) or {}
    return {"ok": True, "key": key, "block": block,
            "note": "drawings are stored in your config file, per view and symbol"}


@router.get("/markers")
async def markers_get(symbol: str = "") -> dict[str, Any]:
    """The pinned levels for one symbol (stored in the config, in data space)."""
    cfg = config_store.load_config()
    key = (symbol or "").upper()[:24]
    return {"ok": True, "key": key, "block": (cfg.get("markers") or {}).get(key) or {"markers": []}}


@router.post("/markers")
async def markers_post(payload: dict = Body(default={})) -> dict[str, Any]:
    """Store the pinned levels for one symbol.

    Sanitised by `config_store` (prices finite and positive, per-symbol cap), and the stored block is
    returned so the panel adopts what the store accepted instead of what it hoped it sent.
    """
    cfg = config_store.load_config()
    key = str(payload.get("symbol") or "").upper()[:24]
    spaces = cfg.setdefault("markers", {})
    if not isinstance(spaces, dict):
        spaces = {}
        cfg["markers"] = spaces
    spaces[key] = {"markers": payload.get("markers") or []}
    saved = config_store.save_config(cfg)
    block = (saved.get("markers") or {}).get(key) or {"markers": []}
    return {"ok": True, "key": key, "block": block,
            "note": "markers are stored in your config file, per symbol"}


@router.get("/params")
async def params_get() -> dict[str, Any]:
    """The display-variable registry with live values.

    One table behind every settings dialog, the Chart menus and the palette: what each knob is, where
    it lives in the config, its bounds, and what it means. `test_param_registry.py` asserts it covers
    every display-relevant variable in the config store.
    """
    from orderflow_system.desktop import param_registry
    return param_registry.dump(config_store.load_config(), config_store.default_config())


@router.get("/ofx")
async def ofx_get() -> dict[str, Any]:
    """The engine's persisted parameters (clamped by config_store on write)."""
    cfg = config_store.load_config()
    return {"ok": True, "ofx": cfg.get("ofx") or {}}


@router.post("/ofx")
async def ofx_save(payload: dict = Body(default={})) -> dict[str, Any]:
    """Persist the engine's parameters. config_store clamps them, so a bad input cannot make
    the renderer unusable."""
    cfg = config_store.load_config()
    ofx = cfg.setdefault("ofx", {})
    for key in ("symbol", "R", "stack", "lambda_ms", "text_px", "sweep_c", "min_block", "va_pct", "ramp"):
        if key in payload:
            ofx[key] = payload[key]
    saved = config_store.save_config(cfg)
    return {"ok": True, "ofx": saved.get("ofx") or {},
            "note": "Stored in your config file; rendering happens in your browser session."}


# ──────────────────────────────────────────────────────────────
# Bar/candle expression (P1-8)
# ──────────────────────────────────────────────────────────────


@router.get("/expression")
async def expression_get() -> dict[str, Any]:
    """How bars are expressed, per chart surface.

    The engine view and the chart view each keep their own mode + palette; the words for whatever is
    chosen are `desktop/ui/expression.js`'s, which the renderers paint from as well. The store clamps
    both keys (config_store.EXPRESSION_MODES / EXPRESSION_PALETTES).
    """
    cfg = config_store.load_config()
    return {"ok": True, "expression": cfg.get("expression") or {},
            "modes": list(config_store.EXPRESSION_MODES),
            "palettes": list(config_store.EXPRESSION_PALETTES)}


@router.post("/expression")
async def expression_save(payload: dict = Body(default={})) -> dict[str, Any]:
    """Persist one chart surface's expression choice.

    Partial by design: the body names the surface (`engine` or `chart`) and only the keys it changes,
    so one surface's control can never blank the other's. Returns the value the STORE accepted (a
    junk mode comes back as `default`, not echoed), which is what the control then displays.
    """
    surface = str(payload.get("chart") or "").strip().lower()
    if surface not in ("engine", "chart"):
        return {"ok": False, "error": "chart must be 'engine' or 'chart'"}
    cfg = config_store.load_config()
    node = cfg.setdefault("expression", {}).setdefault(surface, {})
    for key in ("mode", "palette"):
        if key in payload:
            node[key] = payload[key]
    saved = config_store.save_config(cfg)
    accepted = ((saved.get("expression") or {}).get(surface) or {})
    return {"ok": True, "chart": surface, "value": accepted,
            "expression": saved.get("expression") or {},
            "note": "stored in your config file; the drawing happens in your browser session"}


# ──────────────────────────────────────────────────────────────
# Third-party platform bridge (the DTC platform / the reference platform)
# ──────────────────────────────────────────────────────────────

def _dtc_block(cfg: dict[str, Any]) -> dict[str, Any]:
    """The stored DTC connection settings, coerced to the shape the UI expects."""
    from orderflow_system.desktop import platforms as platform_mod
    stored = ((cfg.get("platforms") or {}).get("sierra") or {})
    block = {**platform_mod.dtc_defaults(), **(stored if isinstance(stored, dict) else {})}
    return block


def _mask_dtc(block: dict[str, Any]) -> dict[str, Any]:
    """Never hand the password back: the UI shows whether one is set, not what it is."""
    safe = {k: v for k, v in block.items() if k != "password"}
    safe["password_set"] = bool(block.get("password"))
    return safe


def _bookmap_block(cfg: dict[str, Any]) -> dict[str, Any]:
    """The stored Bookmap bridge settings, coerced to the shape the UI expects.

    There is nothing secret in here: the bridge is a loopback socket to an add-on that was let in by
    hand, so the block is a host, a port, a symbol and the tier the user says they run.
    """
    from orderflow_system.desktop import platforms as platform_mod
    stored = ((cfg.get("platforms") or {}).get("bookmap") or {})
    return {**platform_mod.bookmap_defaults(), **(stored if isinstance(stored, dict) else {})}


def _mask_bookmap(block: dict[str, Any]) -> dict[str, Any]:
    """Same shape out, with the tier validated against the published tiers and nothing else hidden."""
    from orderflow_system.desktop import platforms as platform_mod
    safe = dict(block)
    safe["plan"] = safe.get("plan") if safe.get("plan") in platform_mod.BOOKMAP_PLAN_IDS else "digital"
    safe["host"] = str(safe.get("host") or "127.0.0.1")
    safe["protocol"] = platform_mod.bookmap_defaults()["protocol"]
    return safe


@router.post("/atlas/footprint")
async def atlas_footprint_save(payload: dict = Body(default={})) -> dict[str, Any]:
    """Save the footprint's analysis settings (imbalance mode/ratio, print-size filter).

    These are analytic choices, not per-symbol data, so they live in the config's
    `atlas.footprint` block: the same convention then applies to the chart, the API and
    the calculated row, across symbols and restarts.
    """
    cfg = config_store.load_config()
    atlas = cfg.setdefault("atlas", {})
    block = dict(atlas.get("footprint") or {})
    for key in ("imbalance_mode", "imbalance_threshold", "equal_tolerance", "min_print_size",
                "show_equal", "show_extremes"):
        if key in payload and payload[key] is not None:
            block[key] = payload[key]
    atlas["footprint"] = block
    saved = config_store.save_config(cfg)
    return {"ok": True, "footprint": saved["atlas"]["footprint"],
            "note": "Print-size filtering applies when the next bars are built."}


@router.get("/platforms")
async def platforms_bridge() -> dict[str, Any]:
    """The platform integrations: workflows, links, plans (free first), local installs, bridge blocks.

    Sierra's keys stay exactly where they were (`sierra`, `plans`, `links`, `workflow`, …) because the
    Platforms view reads them; Bookmap arrives beside them under its own name, and `platforms` carries
    the same rows for anything that wants to render both without hard-coding either.
    """
    from orderflow_system.desktop import platforms as platform_mod

    cfg = config_store.load_config()
    block = _dtc_block(cfg)
    bookmap_block = _bookmap_block(cfg)
    cat = platform_mod.catalogue()
    rows = {row.get("id"): row for row in (cat.get("platforms") or [])}
    platform_row = rows.get("sierra") or (cat.get("platforms") or [{}])[0]
    bookmap_row = rows.get("bookmap") or {}
    installs = await asyncio.to_thread(platform_mod.detect_installs)
    return {
        "ok": True,
        "sierra": _mask_dtc(block),
        "bookmap": _mask_bookmap(bookmap_block),
        "catalogue": cat,
        "plans": platform_row.get("plans", []),
        "links": platform_row.get("links", []),
        "prices_as_of": platform_row.get("prices_as_of", ""),
        "caveats": platform_row.get("caveats", []),
        "workflow": platform_mod.workflow(block.get("plan", "free")),
        "bookmap_plans": bookmap_row.get("plans", []),
        "bookmap_links": bookmap_row.get("links", []),
        "bookmap_prices_as_of": bookmap_row.get("prices_as_of", ""),
        "bookmap_caveats": bookmap_row.get("caveats", []),
        "bookmap_limits": bookmap_row.get("limits", {}),
        "bookmap_workflow": platform_mod.bookmap_workflow(bookmap_block.get("plan", "digital")),
        "bookmap_bridge": platform_mod.bookmap_bridge_state(),
        "installs": installs,
        "suggested_symbols": platform_mod.suggested_symbols(config_store.enabled_symbols(cfg)),
        "free_note": "The free trial and the delayed streaming feed need no payment — start there.",
        "bookmap_free_note": "Bookmap's free tier (Digital) needs an account and no payment: crypto "
                             "depth, one instrument at a time, 1 hour of backfill.",
        "note": "Optional: a DTC server on your own platform can feed this suite directly.",
        "bookmap_note": "Optional: Bookmap has no data-out API, so this suite ships a small read-only "
                        "add-on that republishes its live trades and depth on loopback.",
    }


@router.post("/platforms/open")
async def platforms_open(payload: dict = Body(default={})) -> dict[str, Any]:
    """Open one of the integration's own links in the default browser.

    Allow-listed to the vendor's https pages only: this never opens an arbitrary URL handed to it.
    """
    from orderflow_system.desktop import platforms as platform_mod

    return platform_mod.open_url(str(payload.get("url") or ""))


@router.post("/platforms/plan")
async def platforms_plan(payload: dict = Body(default={})) -> dict[str, Any]:
    """Load an integration into the workflow, or set which plan/tier the user actually runs.

    The plan is a stored fact, not a guess: the view, the workflow steps and the status label all
    read it, and an unknown plan falls back to that platform's free path. `platform` picks which
    integration is being written (default `sierra`, so existing callers keep their meaning).
    """
    from orderflow_system.desktop import platforms as platform_mod

    cfg = config_store.load_config()
    which = str(payload.get("platform") or "sierra").lower()
    bookmap = which == "bookmap"
    ids = platform_mod.BOOKMAP_PLAN_IDS if bookmap else platform_mod.PLAN_IDS
    fallback = "digital" if bookmap else "free"
    block = cfg.setdefault("platforms", {}).setdefault("bookmap" if bookmap else "sierra", {})
    if "plan" in payload:
        plan = str(payload.get("plan") or fallback).lower()
        block["plan"] = plan if plan in ids else fallback
    if "integrated" in payload:
        block["integrated"] = bool(payload["integrated"])
    saved = config_store.save_config(cfg)
    dtc = _dtc_block(saved)
    bm = _bookmap_block(saved)
    return {
        "ok": True,
        "platform": "bookmap" if bookmap else "sierra",
        "sierra": _mask_dtc(dtc),
        "bookmap": _mask_bookmap(bm),
        "plans": platform_mod.BOOKMAP_PLANS if bookmap else platform_mod.PLANS,
        "workflow": (platform_mod.bookmap_workflow(bm.get("plan", "digital")) if bookmap
                     else platform_mod.workflow(dtc.get("plan", "free"))),
        "price_note": f"prices read {platform_mod.BOOKMAP_PRICES_AS_OF if bookmap else platform_mod.PRICES_AS_OF}"
                      f" from the vendor's pricing page",
    }


@router.post("/platforms/bridge/dtc")
async def dtc_settings_save(payload: dict = Body(default={})) -> dict[str, Any]:
    """Save DTC connection settings. Send `password` only to change it; omit it to keep it."""
    cfg = config_store.load_config()
    block = _dtc_block(cfg)
    for key in ("enabled", "host", "port", "use_tls", "symbol", "integrated"):
        if key in payload and payload[key] is not None:
            block[key] = payload[key]
    if "username" in payload and payload["username"] is not None:
        block["username"] = payload["username"]
    if "password" in payload and payload["password"] is not None:
        block["password"] = payload["password"]
    if payload.get("clear_password"):
        block["password"] = ""
    platforms_block = cfg.setdefault("platforms", {})
    platforms_block["sierra"] = block
    saved = config_store.save_config(cfg)
    return {"ok": True, "sierra": _mask_dtc(_dtc_block(saved)),
            "note": "Stored in your per-user config file; never sent anywhere but your own DTC server."}


@router.post("/platforms/bridge/dtc/test")
async def dtc_test(payload: dict = Body(default={})) -> dict[str, Any]:
    """Connect to the DTC server and report what it says — the one-click bridge check.

    Uses the stored settings unless the caller supplies overrides, and returns only the
    server's answers: name, version, capability flags, message counts, a sample. No
    credential appears in the response.
    """
    from orderflow_system.data.dtc_client import dtc_probe

    cfg = config_store.load_config()
    block = _dtc_block(cfg)
    host = str(payload.get("host") or block.get("host") or "127.0.0.1")
    try:
        port = int(payload.get("port") or block.get("port") or 11099)
    except (TypeError, ValueError):
        port = 11099
    symbol = str(payload.get("symbol") or block.get("symbol") or "")
    password = str(payload["password"]) if payload.get("password") is not None else str(block.get("password") or "")
    use_tls = bool(payload.get("use_tls", block.get("use_tls", False)))
    try:
        seconds = min(10.0, max(0.5, float(payload.get("seconds", 3.0) or 3.0)))
    except (TypeError, ValueError):
        seconds = 3.0
    result = await asyncio.to_thread(dtc_probe, host, port, str(block.get("username") or ""),
                                     password, use_tls, symbol, seconds, 6.0)
    return result


@router.post("/platforms/bridge/bookmap")
async def bookmap_settings_save(payload: dict = Body(default={})) -> dict[str, Any]:
    """Save the Bookmap bridge settings. No credentials exist here: it is a loopback socket.

    The add-on is the server; the suite only ever connects to the host/port the add-on printed.
    """
    from orderflow_system.desktop import platforms as platform_mod

    cfg = config_store.load_config()
    block = _bookmap_block(cfg)
    for key in ("enabled", "host", "symbol", "integrated", "addon_built"):
        if key in payload and payload[key] is not None:
            block[key] = payload[key]
    if payload.get("port") is not None:
        try:
            port = int(payload["port"])
        except (TypeError, ValueError):
            port = block.get("port", 8791)
        block["port"] = port if 1 <= port <= 65535 else 8791
    if payload.get("plan") is not None:
        plan = str(payload["plan"]).lower()
        block["plan"] = plan if plan in platform_mod.BOOKMAP_PLAN_IDS else "digital"
    block["protocol"] = platform_mod.bookmap_defaults()["protocol"]
    cfg.setdefault("platforms", {})["bookmap"] = block
    saved = config_store.save_config(cfg)
    return {"ok": True, "bookmap": _mask_bookmap(_bookmap_block(saved)),
            "note": "Stored in your per-user config file; the bridge only ever dials 127.0.0.1."}


@router.post("/platforms/bridge/bookmap/test")
async def bookmap_test(payload: dict = Body(default={})) -> dict[str, Any]:
    """Connect to the bridge add-on and report what it is streaming — the one-click check.

    Uses the stored settings unless the caller supplies overrides. The answer names the add-on, its
    version, the Bookmap build it reported, message counts and one sample row; nothing is stored and
    nothing is sent back to the add-on.
    """
    from orderflow_system.data.bookmap_client import bookmap_probe

    cfg = config_store.load_config()
    block = _bookmap_block(cfg)
    host = str(payload.get("host") or block.get("host") or "127.0.0.1")
    try:
        port = int(payload.get("port") or block.get("port") or 8791)
    except (TypeError, ValueError):
        port = 8791
    symbol = str(payload.get("symbol") or block.get("symbol") or "")
    try:
        seconds = min(10.0, max(0.5, float(payload.get("seconds", 3.0) or 3.0)))
    except (TypeError, ValueError):
        seconds = 3.0
    return await asyncio.to_thread(bookmap_probe, host, port, seconds=seconds, timeout=6.0, symbol=symbol)


@router.get("/platforms/bridge/bookmap/jar")
async def bookmap_jar() -> dict[str, Any]:
    """The add-on jar this install ships: where it is, what it was built for, and whether that
    matches the Bookmap installed here. Read-only — it never opens or runs the jar."""
    from orderflow_system.desktop import platforms as platform_mod

    return {"ok": True, **platform_mod.bookmap_bridge_state()}


@router.post("/platforms/bridge/bookmap/jar/open")
async def bookmap_jar_open(payload: dict = Body(default={})) -> dict[str, Any]:
    """Open the add-on folder so the jar can be picked in Bookmap's API-plugins dialog.

    Accepts no path from the caller except this suite's own folder (the helper re-checks it).
    """
    from orderflow_system.desktop import platforms as platform_mod

    folder = str(payload.get("folder") or "") or None
    return await asyncio.to_thread(platform_mod.reveal_bridge_jar, folder)

# ──────────────────────────────────────────────────────────────
# Engine control
# ──────────────────────────────────────────────────────────────

@router.get("/engine/status")
async def engine_status() -> dict[str, Any]:
    return engine_mod.engine.status()


@router.get("/live-status")
async def live_status() -> dict[str, Any]:
    """Per-endpoint live / warming / demo map — the UI's single source of truth.

    The dashboard's "data:" chip reads this; panels that can still serve demo data
    (tape, footprint, microstructure, …) should never guess their own state.
    """
    return engine_mod.engine.live_status()


@router.post("/engine/start")
async def engine_start(cfg: Optional[dict] = Body(default=None)) -> dict[str, Any]:
    if cfg:
        config_store.save_config(cfg)
    cfg = config_store.load_config()
    logs.install(cfg.get("logging", {}).get("level", "INFO"))
    return await engine_mod.engine.start(cfg)


@router.post("/engine/stop")
async def engine_stop() -> dict[str, Any]:
    return await engine_mod.engine.stop()


@router.post("/engine/restart")
async def engine_restart(cfg: Optional[dict] = Body(default=None)) -> dict[str, Any]:
    if cfg:
        config_store.save_config(cfg)
    return await engine_mod.engine.restart(config_store.load_config())


# ──────────────────────────────────────────────────────────────
# Telegram self-test
# ──────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────
# Alpaca Markets — account linking (see desktop/alpaca.py)
# ──────────────────────────────────────────────────────────────

_ALPACA_CACHE: dict[str, Any] = {"report": None, "at": 0.0}


def _alpaca_cfg() -> dict[str, Any]:
    cfg = config_store.load_config()
    return dict(cfg.get("alpaca") or {})


def _alpaca_client(cfg: dict[str, Any]):
    from orderflow_system.desktop import alpaca as alpaca_mod

    return alpaca_mod.AlpacaClient(cfg.get("key_id", ""), cfg.get("secret", ""),
                                   bool(cfg.get("paper", True)))


@router.get("/alpaca/status")
async def alpaca_status(refresh: bool = Query(default=False)) -> dict[str, Any]:
    """Saved-account state plus (cached) capability report. Never returns the secret."""
    from orderflow_system.desktop import alpaca as alpaca_mod

    cfg = _alpaca_cfg()
    out: dict[str, Any] = {
        "configured": bool(cfg.get("key_id") and cfg.get("secret")),
        "enabled": bool(cfg.get("enabled")),
        "paper": bool(cfg.get("paper", True)),
        "key_masked": alpaca_mod.mask_key(str(cfg.get("key_id") or "")),
        "view_symbols": list(cfg.get("view_symbols") or []),
    }
    now = time.time()
    if refresh or not _ALPACA_CACHE["report"] or now - float(_ALPACA_CACHE["at"]) > 120:
        if out["configured"]:
            report = await asyncio.to_thread(alpaca_mod.probe, cfg)
            _ALPACA_CACHE["report"] = report
            _ALPACA_CACHE["at"] = now
        else:
            out["report"] = None
            return out
    out["report"] = _ALPACA_CACHE["report"]
    return out


@router.post("/alpaca/test")
async def alpaca_test(payload: dict = Body(default={})) -> dict[str, Any]:
    """Validate a key pair against Alpaca and report what the account can reach."""
    from orderflow_system.desktop import alpaca as alpaca_mod

    cfg = _alpaca_cfg()
    body = {
        "key_id": payload.get("key_id") or cfg.get("key_id", ""),
        "secret": payload.get("secret") or cfg.get("secret", ""),
        "paper": payload.get("paper", cfg.get("paper", True)),
    }
    report = await asyncio.to_thread(alpaca_mod.probe, body)
    if report.get("ok") and payload.get("save"):
        cfg.update({"key_id": body["key_id"], "secret": body["secret"],
                    "paper": bool(body["paper"]), "enabled": True})
        saved = config_store.save_config(cfg) if hasattr(config_store, "save_config") else None
        report["saved"] = bool(saved if saved is not None else True)
        _ALPACA_CACHE.update({"report": report, "at": time.time()})
    return report


@router.post("/alpaca/save")
async def alpaca_save(payload: dict = Body(default={})) -> dict[str, Any]:
    """Store the keys locally (config file, same place as the alert credentials)."""
    from orderflow_system.desktop import alpaca as alpaca_mod

    cfg = _alpaca_cfg()
    if "key_id" in payload:
        cfg["key_id"] = str(payload.get("key_id") or "").strip()
    if "secret" in payload and str(payload.get("secret") or ""):
        cfg["secret"] = str(payload.get("secret") or "").strip()
    if "paper" in payload:
        cfg["paper"] = bool(payload["paper"])
    if "enabled" in payload:
        cfg["enabled"] = bool(payload["enabled"])
    if "view_symbols" in payload and isinstance(payload["view_symbols"], list):
        cfg["view_symbols"] = [str(x).strip().upper() for x in payload["view_symbols"] if str(x).strip()][:30]
    whole = config_store.load_config()
    whole["alpaca"] = cfg
    config_store.save_config(whole)
    _ALPACA_CACHE.update({"report": None, "at": 0.0})
    return {"ok": True, "enabled": bool(cfg.get("enabled")), "paper": bool(cfg.get("paper")),
            "key_masked": alpaca_mod.mask_key(str(cfg.get("key_id") or ""))}


@router.post("/alpaca/clear")
async def alpaca_clear() -> dict[str, Any]:
    """Forget the keys entirely."""
    whole = config_store.load_config()
    whole["alpaca"] = {**(whole.get("alpaca") or {}), "key_id": "", "secret": "", "enabled": False}
    config_store.save_config(whole)
    _ALPACA_CACHE.update({"report": None, "at": 0.0})
    return {"ok": True, "cleared": True}


# ──────────────────────────────────────────────────────────────
# Search (plan Phase 4) — the palette's market side
# ──────────────────────────────────────────────────────────────

_SEARCH: dict[str, Any] = {"universe": None, "batcher": None, "pump": None,
                           "active": [], "view": "", "last_active": 0.0, "data": None}


def _search_data():
    """A shared AlpacaData for the palette (assets + clock), built once."""
    from orderflow_system.data.alpaca_feed import AlpacaData

    cfg = _alpaca_cfg()
    key_id = str(cfg.get("key_id") or "")
    secret = str(cfg.get("secret") or "")
    feed = str(cfg.get("feed") or "iex")
    data = _SEARCH.get("data")
    if data is None or (data.key_id, data.secret, data.feed) != (key_id, secret, feed):
        data = AlpacaData(key_id, secret, feed=feed, cache_dir=str(config_store.config_dir()))
        _SEARCH["data"] = data
    return data


def _search_live_provider(symbol: str) -> dict[str, Any]:
    """Live fields for one palette row — from the engine, never invented."""
    system = engine_mod.engine.system
    if system is None:
        return {}
    key = str(symbol or "").upper()
    if not key:
        return {}
    out: dict[str, Any] = {}
    # The palette lists app symbols, but the rows that arrive from Alpaca wear
    # Alpaca's spelling (BTC/USD): map both ways through the capability block.
    caps = engine_mod.alpaca_capability_block(config_store.load_config(), None)
    app_symbol = key
    for app, alp in (caps.get("symbols") or {}).items():
        if key in (str(app).upper(), str(alp).upper()):
            app_symbol = app
            break
    pipeline = getattr(system, "pipelines", {}).get(app_symbol)
    # 128 prints is roughly a minute on a busy tape: wide enough that the %-change
    # means something, small enough that it still describes "now".
    ticks = system.recent_ticks(app_symbol, 128) if hasattr(system, "recent_ticks") else []
    if ticks:
        prices = [t.price for t in ticks]
        out["last"] = round(prices[-1], 6)
        if prices[0]:
            out["chg_pct"] = round((prices[-1] - prices[0]) / prices[0] * 100.0, 3)
        out["chg_help"] = f"change across the last {len(prices)} prints"
        out["volume"] = round(sum(t.size for t in ticks), 6)
        out["spark"] = [round(p, 6) for p in prices[-32:]]
    if pipeline is not None:
        feed = getattr(system, "alpaca_feed", None)
        if feed is not None and app_symbol in getattr(feed, "symbols", {}):
            out["subscribed"] = app_symbol in (feed.subscriptions.trades + feed.subscriptions.quotes)
            out["depth"] = False
        else:
            out["depth"] = True
    return out


def _search_universe() -> Any:
    from orderflow_system.desktop import search_service

    cfg = config_store.load_config()
    alp = dict(cfg.get("alpaca") or {})
    linked = bool(alp.get("key_id") and alp.get("secret"))
    caps = engine_mod.alpaca_capability_block(cfg, (_ALPACA_CACHE.get("report") if linked else None))
    feed = getattr(engine_mod.engine.system, "alpaca_feed", None) if engine_mod.engine.system else None
    clock = getattr(feed, "last_clock", None) if feed is not None else None
    data = _search_data() if linked else None
    source = str((getattr(engine_mod.engine, "_source", "") or cfg.get("data_source") or ""))
    local_feeds = {}
    for symbol in config_store.enabled_symbols(cfg):
        spec = config_store.instrument_cfg(cfg, symbol) or {"symbol": symbol}
        if source == "alpaca" and symbol in (caps.get("symbols") or {}):
            local_feeds[symbol] = str(alp.get("feed") or "iex")
        elif source in ("bybit", "both") and engine_mod.bybit_capable(spec):
            local_feeds[symbol] = "bybit"
        elif source in ("mt5", "both"):
            local_feeds[symbol] = "mt5"
    universe = search_service.SymbolUniverse(
        config=cfg,
        assets_provider=(data.assets if data else None),
        clock_provider=(lambda: clock) if clock else None,
        live_provider=_search_live_provider,
        alpaca_linked=linked,
        alpaca_feed=str(alp.get("feed") or "iex"),
        alpaca_symbols=caps.get("symbols") or {},
        local_feeds=local_feeds,
    )
    return universe


async def _search_pump() -> None:
    """Push batched row updates for the palette's active symbols.

    One task, started when the palette first asks for live rows and stopped when it
    has been idle for two minutes — no polling loop runs forever for a closed palette.
    """
    from orderflow_system.dashboard.app import ws_manager

    while True:
        try:
            await asyncio.sleep(0.25)
            if not _SEARCH["active"]:
                if time.time() - float(_SEARCH["last_active"] or 0) > 120:
                    _SEARCH["pump"] = None
                    return
                continue
            batcher = _SEARCH.get("batcher")
            if batcher is None:
                continue
            for symbol in list(_SEARCH["active"]):
                patch = _search_live_provider(symbol)
                if patch:
                    batcher.offer(symbol, patch)
            rows = batcher.drain()
            if rows:
                await ws_manager.broadcast_search_rows(rows)
        except asyncio.CancelledError:
            raise
        except Exception:                       # noqa: BLE001 — the palette must never kill the app
            logger.debug("search pump tick failed", exc_info=True)


@router.get("/search/symbols")
async def search_symbols(q: str = Query(default=""), limit: int = Query(default=20),
                         sort: str = Query(default=""), types: str = Query(default="")) -> dict[str, Any]:
    """Ranked symbol rows for the palette: pins → recents → local → Alpaca assets → crypto."""
    from orderflow_system.desktop import search_service

    cfg = config_store.load_config()
    universe = _search_universe()
    wanted = [t.strip() for t in str(types or "").split(",") if t.strip()]
    payload = universe.search(q, limit=limit, sort=(sort or cfg.get("search", {}).get("sort") or "relevance"),
                              types=wanted)
    payload["feeds"] = {key: {"label": label[0], "help": label[1],
                              "delivery": search_service.FEED_DELIVERY.get(key, "realtime")}
                        for key, label in search_service.FEED_LABELS.items()}
    return payload


@router.post("/search/active")
async def search_active(payload: dict = Body(default={})) -> dict[str, Any]:
    """The palette tells us which rows are visible: those are the ones that update."""
    from orderflow_system.desktop.search_service import RowBatcher

    symbols = [str(s).strip().upper() for s in (payload.get("symbols") or []) if str(s).strip()][:60]
    _SEARCH["active"] = symbols
    _SEARCH["view"] = str(payload.get("view") or "")
    _SEARCH["last_active"] = time.time()
    if _SEARCH.get("batcher") is None:
        _SEARCH["batcher"] = RowBatcher()
    if symbols and _SEARCH.get("pump") is None:
        _SEARCH["pump"] = asyncio.ensure_future(_search_pump())

    # remember the choice: recents drive the empty-state list and the ranking boost
    focus = str(payload.get("focus") or "").strip().upper()
    if focus:
        cfg = config_store.load_config()
        recents = [r for r in (cfg.get("search", {}).get("recents") or []) if r.upper() != focus]
        recents.insert(0, focus)
        cfg.setdefault("search", {})["recents"] = recents[:12]
        try:
            config_store.save_config(cfg)
        except Exception:                        # noqa: BLE001 — never fail the palette on a save
            logger.debug("recents save failed", exc_info=True)

    rows = [_search_row_snapshot(s) for s in symbols]
    return {"ok": True, "active": len(symbols), "rows": [r for r in rows if r],
            "counters": (_SEARCH["batcher"].counters() if _SEARCH.get("batcher") else {})}


def _search_row_snapshot(symbol: str) -> Optional[dict[str, Any]]:
    patch = _search_live_provider(symbol)
    if not patch:
        return None
    return {"symbol": symbol, **patch}


@router.get("/search/rows")
async def search_rows() -> dict[str, Any]:
    """The latest batched rows — the fallback path when the socket is not connected."""
    batcher = _SEARCH.get("batcher")
    if batcher is None:
        return {"ok": True, "rows": [], "counters": {}}
    return {"ok": True, "rows": batcher.drain(force=True), "counters": batcher.counters(),
            "pending": batcher.pending()}


@router.get("/search/meta")
async def search_meta() -> dict[str, Any]:
    """Counters for the Logs view: what the batcher saw, coalesced and dropped."""
    batcher = _SEARCH.get("batcher")
    cfg = config_store.load_config()
    universe = _search_universe()
    return {
        "ok": True,
        "counters": batcher.counters() if batcher else {"seen": 0, "coalesced": 0, "dropped": 0,
                                                        "batches": 0, "rows_sent": 0},
        "pending": batcher.pending() if batcher else 0,
        "window_ms": batcher.window_ms if batcher else 300,
        "max_symbols": batcher.max_symbols if batcher else 200,
        "active": list(_SEARCH["active"]),
        "assets": universe.asset_count(),
        "linked": bool((cfg.get("alpaca") or {}).get("key_id")),
        "recents": list((cfg.get("search") or {}).get("recents") or []),
        "pins": list((cfg.get("search") or {}).get("pins") or []),
        "watchlist": list(cfg.get("watchlist") or []),
        "default_view": (cfg.get("search") or {}).get("default_view", "orderflow"),
    }


@router.get("/search/watchlist")
async def search_watchlist() -> dict[str, Any]:
    cfg = config_store.load_config()
    return {"ok": True, "watchlist": list(cfg.get("watchlist") or [])}


@router.post("/search/watchlist")
async def search_watchlist_set(payload: dict = Body(default={})) -> dict[str, Any]:
    """Add / remove / clear the watchlist (multi-select in the palette ports here)."""
    cfg = config_store.load_config()
    current = [str(s).upper() for s in (cfg.get("watchlist") or [])]
    if payload.get("clear"):
        current = []
    for symbol in [str(s).strip().upper() for s in (payload.get("add") or []) if str(s).strip()]:
        if symbol not in current:
            current.append(symbol)
    for symbol in [str(s).strip().upper() for s in (payload.get("remove") or []) if str(s).strip()]:
        current = [s for s in current if s != symbol]
    cfg["watchlist"] = current[:60]
    saved = config_store.save_config(cfg)
    return {"ok": True, "watchlist": list(saved.get("watchlist") or [])}


@router.get("/alpaca/chain")
async def alpaca_chain(underlying: str = Query(default=""), expiry: str = Query(default=""),
                       type: str = Query(default=""), strike_min: float = Query(default=None),
                       strike_max: float = Query(default=None), limit: int = Query(default=400)) -> dict[str, Any]:
    """Option chain for one underlying (Alpaca's snapshot endpoint)."""
    from orderflow_system.desktop import search_service

    cfg = _alpaca_cfg()
    if not (cfg.get("key_id") and cfg.get("secret")):
        return {"ok": False, "stage": "keys", "reason": "Link an Alpaca account to read the option chain.",
                "help": "Alpaca quotes are indicative on the free plan; keys take an email to create."}
    symbol = (underlying or "").strip().upper()
    if not symbol:
        return {"ok": False, "reason": "underlying is required"}
    client = _alpaca_client(cfg)
    status, body = await asyncio.to_thread(
        client.call,
        f"https://data.alpaca.markets/v1beta1/options/snapshots/{symbol}",
        {"feed": "indicative", "limit": str(min(int(limit or 400), 1000))})
    if status != 200:
        return {"ok": False, "stage": "api", "reason": f"Alpaca answered HTTP {status} for {symbol}.",
                "detail": str(body)[:200]}
    rows = search_service.chain_rows(body, expiry=expiry, strike_min=strike_min,
                                     strike_max=strike_max, option_type=type, limit=limit)
    return {
        "ok": True,
        "underlying": symbol,
        "expiries": search_service.normalize_expiries(body),
        "summary": search_service.with_greeks_summary(rows),
        "rows": rows,
        "feed": "indicative",
        "feed_label": search_service.feed_label("indicative"),
        "live_subscription": {
            "available": False,
            "reason": ("Per-contract live quotes need Alpaca's streaming options feed, which is "
                       "MsgPack-only — deferred (plan decision D-A) so the program keeps zero new "
                       "dependencies. Snapshots refresh on demand instead."),
        },
    }


@router.get("/alpaca/compare")
async def alpaca_compare(symbol: str = Query(default="AAPL")) -> dict[str, Any]:
    """Two feeds, side by side: entitlement-gated, never promising what is not there."""
    from orderflow_system.desktop import search_service

    cfg = _alpaca_cfg()
    caps_report = _ALPACA_CACHE.get("report") or {}
    entitled_sip = bool((caps_report.get("capabilities") or {}).get("equities_sip_delayed"))
    symbol = (symbol or "").strip().upper()
    out: dict[str, Any] = {"ok": True, "symbol": symbol, "pairs": [], "notes": []}
    linked = bool(cfg.get("key_id") and cfg.get("secret"))

    if linked and "/" not in symbol:
        client = _alpaca_client(cfg)
        st_iex, body_iex = await asyncio.to_thread(client.latest_trade, symbol, "iex")
        out["pairs"].append({"feed": "iex", "label": search_service.feed_label("iex"),
                             "last": ((body_iex or {}).get("trade") or {}).get("p"),
                             "as_of": ((body_iex or {}).get("trade") or {}).get("t"),
                             "ok": st_iex == 200})
        if entitled_sip:
            st_sip, body_sip = await asyncio.to_thread(client.latest_trade, symbol, "sip")
            out["pairs"].append({"feed": "sip", "label": search_service.feed_label("sip"),
                                 "last": ((body_sip or {}).get("trade") or {}).get("p"),
                                 "as_of": ((body_sip or {}).get("trade") or {}).get("t"),
                                 "ok": st_sip == 200})
        else:
            st_delayed, body_delayed = await asyncio.to_thread(client.bars_aged, symbol, 20, "sip", 2)
            delayed_last = None
            if st_delayed == 200 and isinstance(body_delayed, dict) and body_delayed.get("bars"):
                delayed_last = body_delayed["bars"][-1].get("c")
            out["pairs"].append({"feed": "delayed_sip", "label": search_service.feed_label("delayed_sip"),
                                 "last": delayed_last, "ok": st_delayed == 200,
                                 "note": "readable 15 minutes behind on the free plan"})
            out["notes"].append("SIP real-time is not included on this plan — the delayed window is shown instead.")
    else:
        out["notes"].append("Link an Alpaca account to compare its feeds against the exchange.")

    # Alpaca crypto vs the exchange's own price for the same market
    if "/" in symbol or symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        pair = {"BTCUSDT": "BTC/USD", "ETHUSDT": "ETH/USD", "SOLUSDT": "SOL/USD"}.get(symbol, symbol)
        data = _search_data()
        status, body = await asyncio.to_thread(data.call,
                                               "https://data.alpaca.markets/v1beta3/crypto/us/latest/trades",
                                               {"symbols": pair}, False)
        alpaca_last = None
        if status == 200 and isinstance(body, dict):
            trades = body.get("trades") or {}
            alpaca_last = (trades.get(pair) or {}).get("p")
        live = _search_live_provider(symbol if symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT") else pair)
        out["pairs"].append({"feed": "alpaca_crypto", "label": search_service.feed_label("alpaca_crypto"),
                             "last": alpaca_last, "ok": status == 200})
        out["pairs"].append({"feed": "bybit", "label": search_service.feed_label("bybit"),
                             "last": live.get("last"), "ok": bool(live.get("last"))})

    prices = [p["last"] for p in out["pairs"] if p.get("last")]
    out["spread"] = round(max(prices) - min(prices), 6) if len(prices) > 1 else None
    out["available"] = len(out["pairs"]) >= 2
    if not out["available"] and not out["notes"]:
        out["notes"].append("Not enough reachable feeds for this symbol to compare.")
    return out


@router.get("/alpaca/feed")
async def alpaca_feed_status() -> dict[str, Any]:
    """Live state of the Alpaca data feed (REST budget, streams, subscriptions)."""
    feed = getattr(engine_mod.engine.system, "alpaca_feed", None) if engine_mod.engine.system else None
    base = {"running": feed is not None, "config": {"feed": _alpaca_cfg().get("feed", "iex"),
                                                    "paper": bool(_alpaca_cfg().get("paper", True))}}
    if feed is None:
        base["state"] = "idle"
        base["note"] = ("The Alpaca feed starts with the engine when the data source includes "
                        "Alpaca — choose it in Settings → Data source.")
        return base
    base.update(feed.status())
    return base


@router.get("/alpaca/subscriptions")
async def alpaca_subscriptions() -> dict[str, Any]:
    feed = getattr(engine_mod.engine.system, "alpaca_feed", None) if engine_mod.engine.system else None
    if feed is None:
        return {"ok": True, "running": False, "subscriptions": {"trades": [], "quotes": [], "bars": [],
                                                                "count": 0, "warnings": []},
                "symbols": _alpaca_cfg().get("view_symbols") or []}
    return {"ok": True, "running": True, "subscriptions": feed.subscriptions.as_dict(),
            "symbols": feed.symbols, "status": feed.status()}


@router.post("/alpaca/subscriptions")
async def alpaca_subscribe(payload: dict = Body(default={})) -> dict[str, Any]:
    """Add/remove stream symbols. Idempotent: the UI may call it on every change."""
    feed = getattr(engine_mod.engine.system, "alpaca_feed", None) if engine_mod.engine.system else None
    if feed is None:
        return {"ok": False, "error": "the Alpaca feed is not running — start the engine with Alpaca as its source"}
    channel = str(payload.get("channel") or "trades")
    added = await feed.streams[0].subscribe(channel, payload.get("add") or []) if feed.streams else []
    removed = await feed.streams[0].unsubscribe(channel, payload.get("remove") or []) if feed.streams else []
    return {"ok": True, "channel": channel, "added": added, "removed": removed,
            "subscriptions": feed.subscriptions.as_dict()}


@router.get("/alpaca/portfolio")
async def alpaca_portfolio() -> dict[str, Any]:
    """Read-only account view: positions, recent orders, portfolio history."""
    cfg = _alpaca_cfg()
    if not (cfg.get("key_id") and cfg.get("secret")):
        return {"ok": False, "error": "no Alpaca account linked"}

    def _read() -> dict[str, Any]:
        client = _alpaca_client(cfg)
        out: dict[str, Any] = {"ok": True, "paper": bool(cfg.get("paper", True))}
        st, pos = client.positions()
        out["positions"] = pos if st == 200 and isinstance(pos, list) else []
        st, orders = client.orders(limit=25)
        out["orders"] = orders if st == 200 and isinstance(orders, list) else []
        st, hist = client.portfolio_history(period="1M", timeframe="1D")
        out["history"] = hist if st == 200 and isinstance(hist, dict) else None
        return out

    return await asyncio.to_thread(_read)


@router.post("/mt5/test")
async def mt5_test(payload: dict = Body(default={})) -> dict[str, Any]:
    """Prove the MetaTrader 5 bridge works with the settings just typed in.

    Runs the blocking MT5 calls off the event loop. Stages: platform → package →
    terminal → ready, so the setup assistant can name the missing piece.
    """
    return await asyncio.to_thread(engine_mod.mt5_probe, dict(payload or {}))


@router.post("/telegram/test")
async def telegram_test(payload: dict = Body(default={})) -> dict[str, Any]:
    cfg = config_store.load_config()
    token = str(payload.get("bot_token") or cfg["telegram"].get("bot_token") or "").strip()
    chat_id = str(payload.get("chat_id") or cfg["telegram"].get("chat_id") or "").strip()
    if not token or not chat_id:
        return {"ok": False, "error": "Bot token and chat id are both required"}

    from orderflow_system.alerts.telegram_bot import TelegramAlertBot

    bot = TelegramAlertBot(bot_token=token, chat_id=chat_id)
    await bot.initialize()
    if not bot._enabled or bot._bot is None:
        return {"ok": False, "error": "Telegram rejected the bot token (check it in Settings)"}
    try:
        me = await bot._bot.get_me()
        await bot._bot.send_message(
            chat_id=chat_id,
            text="✅ ModFlow OrderFlow Analysis Suite — Telegram alerts are wired up correctly.",
        )
        return {"ok": True, "bot": f"@{me.username}"}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ──────────────────────────────────────────────────────────────
# Volume profile / bias helpers
# ──────────────────────────────────────────────────────────────

@router.post("/profiles/rebuild")
async def rebuild_profiles() -> dict[str, Any]:
    """Force a volume-profile rebuild from the candle history in the database.

    The engine only rebuilds profiles once an hour, so a freshly started
    session shows an empty profile (and therefore no bias / qualified levels)
    for up to 60 minutes. This makes it on-demand.
    """
    system = engine_mod.engine.system
    if system is None:
        return {"ok": False, "error": "Engine is not running — start it first."}

    from datetime import datetime, timezone

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = now_ms - 24 * 3600 * 1000
    results = []
    for sym, pipeline in system.pipelines.items():
        try:
            candles = await system.db.get_candles(sym, "1m", start_ms, now_ms)
            before = len(pipeline.profile_framing._profile_history)
            await system._rebuild_volume_profile(sym, pipeline)
            after = len(pipeline.profile_framing._profile_history)
            results.append({
                "symbol": sym,
                "candles": len(candles),
                "profiles": after,
                "created": after > before,
                "detail": "" if len(candles) >= 10 else "needs at least 10 closed candles in the database",
            })
        except Exception as exc:
            results.append({"symbol": sym, "error": f"{type(exc).__name__}: {exc}"})
    return {"ok": True, "results": results}


@router.get("/profiles/status")
async def profiles_status() -> dict[str, Any]:
    system = engine_mod.engine.system
    if system is None:
        return {"ok": False, "error": "Engine is not running", "symbols": []}
    out = []
    for sym, pipeline in system.pipelines.items():
        framing = pipeline.profile_framing
        bias = framing.current_bias
        out.append({
            "symbol": sym,
            "profiles": len(framing._profile_history),
            "bias": getattr(getattr(bias, "direction", None), "value", None),
            "qualified_levels": len(getattr(bias, "qualified_levels", []) or []),
            "watching": len(system.aggregator._watched_levels.get(sym, [])),
        })
    return {"ok": True, "symbols": out}


# ──────────────────────────────────────────────────────────────
# Logs
# ──────────────────────────────────────────────────────────────

@router.get("/logs")
async def get_logs(lines: int = Query(default=200, le=1000), level: str = Query(default="")) -> dict[str, Any]:
    return {"lines": logs.tail(lines=lines, min_level=level)}


# ──────────────────────────────────────────────────────────────
# History — the archive backfill and reading our own stored ticks
# ──────────────────────────────────────────────────────────────
# The suite's panels are live views; this is the one place that can fill in the past. The pass runs
# on its own database connection (WAL + busy timeout), so it works whether the engine is streaming
# or stopped, and it never touches the live head: rows go in behind it, a window at a time.

#: One job at a time. Two passes would double the archive traffic for no gain, and "is it still
#: running?" would stop having an answer.
_backfill_job: dict[str, Any] = {"state": "idle"}


def _backfill_job_public() -> dict[str, Any]:
    return dict(_backfill_job)


async def _run_backfill(symbol: str, days: list[Any]) -> None:
    from orderflow_system.data import backfill as backfill_mod
    from orderflow_system.data.database import Database

    job = _backfill_job
    db = Database(str(config_store.db_path()))
    try:
        await db.connect()
        job["stage"] = "download"

        def progress(stage: str, **fields: Any) -> None:
            job["stage"] = stage
            for key in ("ticks", "bytes", "cached", "deleted"):
                if key in fields:
                    job[key] = fields[key]

        result = await backfill_mod.backfill_range(
            db, symbol, days, cache_dir=config_store.backfill_cache_dir(), progress=progress)
        job.update(state="done", stage="done", ticks=result["ticks"],
                   days_done=result["days"], days_without_prints=result["days_without_prints"],
                   finished_at=time.time())
        logger.info("backfill: %s complete — %d ticks over %d day(s)",
                    symbol, result["ticks"], len(result["days"]))
    except Exception as exc:
        job.update(state="failed", error=f"{type(exc).__name__}: {exc}", finished_at=time.time())
        logger.warning("backfill failed for %s: %s", symbol, exc, exc_info=True)
    finally:
        try:
            await db.close()
        except Exception:                          # pragma: no cover - closing must never mask a result
            logger.debug("backfill db close failed", exc_info=True)


@router.get("/backfill")
async def backfill_status() -> dict[str, Any]:
    """The state of the (single) backfill job — idle, running, done or failed."""
    return {"ok": True, "job": _backfill_job_public()}


@router.post("/backfill")
async def backfill_start(payload: dict = Body(default={})) -> dict[str, Any]:
    """Fetch stored history for one configured instrument from the venue's public archive.

    Body: {"symbol": "BTCUSDT", "from": "YYYY-MM-DD", "to": "YYYY-MM-DD"} (both days inclusive), or
    {"symbol": ..., "days": ["YYYY-MM-DD", ...]}. At most 7 days per request; the archive does not
    publish today or the future, and a request that asks for either is refused with the reason.
    """
    from orderflow_system.data import backfill as backfill_mod

    symbol = str(payload.get("symbol") or "").strip().upper()
    cfg = config_store.load_config()
    known = {str(i.get("symbol", "")).upper() for i in (cfg.get("instruments") or [])}
    if not symbol or symbol not in known:
        return {"ok": False, "error": f"{symbol or '(none)'} is not one of the configured instruments"}
    if _backfill_job.get("state") == "running":
        return {"ok": False, "error": "a backfill is already running", "job": _backfill_job_public()}

    try:
        if payload.get("days"):
            days = sorted({backfill_mod.parse_day(d) for d in payload["days"]})
        else:
            first = backfill_mod.parse_day(payload.get("from"))
            last = backfill_mod.parse_day(payload.get("to") or payload.get("from"))
            if last < first:
                return {"ok": False, "error": "`to` is before `from`"}
            days = [first + dt.timedelta(days=n) for n in range((last - first).days + 1)]
        if len(days) > backfill_mod.MAX_DAYS_PER_REQUEST:
            return {"ok": False,
                    "error": f"at most {backfill_mod.MAX_DAYS_PER_REQUEST} days per request "
                             f"(asked for {len(days)})"}
        today = dt.datetime.now(dt.timezone.utc).date()
        if any(day >= today for day in days):
            return {"ok": False, "error": "the archive does not publish today or the future yet"}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    _backfill_job.clear()
    _backfill_job.update({
        "state": "running", "symbol": symbol, "days": [d.isoformat() for d in days],
        "stage": "starting", "ticks": 0, "started_at": time.time(),
    })
    asyncio.create_task(_run_backfill(symbol, days))
    return {"ok": True, "job": _backfill_job_public()}


@router.get("/trades")
async def trades(symbol: str = Query(default=""), since: Optional[int] = Query(default=None),
                 until: Optional[int] = Query(default=None),
                 limit: int = Query(default=5_000, ge=1, le=50_000)) -> dict[str, Any]:
    """Read stored ticks for one instrument — the suite's own trade history, in a plain shape.

    The window is capped at 24 h and the page at `limit` rows (newest kept), because a day of a
    liquid instrument is millions of prints. Each row is
    {"ts": <ms>, "price": …, "size": …, "side": "buy"|"sell", "trade_id": …} — the same conventions
    the feed publishes, so a caller cannot tell a backfilled row from a live one.
    """
    from orderflow_system.data.database import Database

    symbol = str(symbol or "").strip().upper()
    cfg = config_store.load_config()
    known = {str(i.get("symbol", "")).upper() for i in (cfg.get("instruments") or [])}
    if not symbol or symbol not in known:
        return {"ok": False, "error": f"{symbol or '(none)'} is not one of the configured instruments"}
    now_ms = int(time.time() * 1000)
    start = int(since) if since is not None else now_ms - 3_600_000
    end = int(until) if until is not None else now_ms
    if end <= start:
        return {"ok": False, "error": "`until` must be after `since`"}
    if end - start > 86_400_000:
        return {"ok": False, "error": "a window is capped at 24 h — narrow it and ask again"}

    db = Database(str(config_store.db_path()))
    try:
        await db.connect()
        total = await db.count_ticks(symbol, start, end)
        ticks = await db.get_recent_ticks(symbol, start, end, limit=limit)
    finally:
        try:
            await db.close()
        except Exception:                          # pragma: no cover
            logger.debug("trades read: db close failed", exc_info=True)

    return {
        "ok": True, "symbol": symbol, "from": start, "to": end,
        "count": len(ticks), "total": total, "truncated": total > len(ticks),
        "ticks": [
            {"ts": t.timestamp_ms, "price": t.price, "size": t.size,
             "side": t.side.value, "trade_id": t.trade_id}
            for t in ticks
        ],
    }


# ──────────────────────────────────────────────────────────────
# Storage (R5: retention has numbers, and the numbers have a window)
# ──────────────────────────────────────────────────────────────

_storage_cache: dict[str, Any] = {"at": 0.0, "data": None}


@router.get("/storage")
async def get_storage(refresh: int = Query(default=0)) -> dict[str, Any]:
    """DB size, row counts, retention settings and the last prune — cached 30 s.

    `COUNT(*)` over a 800 MB ticks table is not a free read, so this answers from a short
    cache (`?refresh=1` forces a fresh read). With the engine stopped the file sizes are
    still real; row counts say so instead of guessing.
    """
    import time as _time

    now = _time.time()
    if not refresh and _storage_cache["data"] is not None and now - _storage_cache["at"] < 30:
        return _storage_cache["data"]

    from orderflow_system.config import settings as rt_settings
    from orderflow_system.desktop import engine as engine_mod

    system = getattr(engine_mod.engine, "_system", None)
    if system is not None and getattr(system, "db", None) is not None:
        snap = await system.db.storage_snapshot()
        last_prune = getattr(system, "_last_prune", None)
    else:
        snap = {"db_path": str(config_store.db_path()), "bytes": 0, "wal_bytes": 0,
                "tables": {}, "ticks": {"oldest_ms": 0, "newest_ms": 0}}
        try:
            from pathlib import Path as _Path
            p = _Path(snap["db_path"])
            snap["bytes"] = p.stat().st_size if p.exists() else 0
            w = _Path(snap["db_path"] + "-wal")
            snap["wal_bytes"] = w.stat().st_size if w.exists() else 0
        except OSError:
            pass
        last_prune = None

    out = dict(snap)
    out["engine_running"] = system is not None
    if system is not None:
        rt = (int(getattr(rt_settings, "RETENTION_DAYS", 30) or 0),
              int(getattr(rt_settings, "PRUNE_INTERVAL_HOURS", 6) or 6),
              int(getattr(rt_settings, "SESSION_START_HOUR", 0) or 0))
    else:
        # The engine applies the config at start; until then, read the file so the panel
        # shows the configured window instead of the Python defaults (a display lie is a lie).
        from orderflow_system.desktop.engine import clamp_data_settings
        _sh, _rd, _ph = clamp_data_settings(config_store.load_config())
        rt = (_rd, _ph, _sh)
    out["retention"] = {"days": rt[0], "prune_interval_hours": rt[1], "session_start_hour": rt[2]}
    out["last_prune"] = last_prune
    _storage_cache["at"] = now
    _storage_cache["data"] = out
    return out


@router.post("/storage/prune")
async def prune_storage_now() -> dict[str, Any]:
    """Run one retention pass now (the periodic job's own path). 409 without an engine: the
    prune needs the live DB handle, not a second writer."""
    from orderflow_system.desktop import engine as engine_mod

    system = getattr(engine_mod.engine, "_system", None)
    if system is None:
        raise HTTPException(status_code=409, detail="engine is not running — start it to prune storage")
    summary = await system._prune_storage()
    _storage_cache["at"] = 0.0
    _storage_cache["data"] = None
    return {"ok": True, "summary": summary}


@router.post("/logs/clear")
async def clear_logs() -> dict[str, Any]:
    logs._buffer.clear()
    return {"ok": True}


# ──────────────────────────────────────────────────────────────
# Workspaces (named layouts; they live in the config file, not a browser)
# ──────────────────────────────────────────────────────────────


def _exports_dir() -> Path:
    """The user's exports folder, beside the config and the log."""
    make = globals().get("config_dir")
    base = None
    if callable(make):
        try:
            base = Path(make())
        except Exception:
            base = None
    if base is None:
        base = Path(os.environ.get("APPDATA") or Path.home()) / "OrderFlowAnalysisPro"
    return base / "exports"


@router.post("/export/save")
async def export_save(payload: dict = Body(default={})) -> dict[str, Any]:
    """Write an export to the user's exports folder and return its path.

    The desktop shell has no download shelf, so "export" has to mean a real file in a known place.
    The name is reduced to a leaf filename: nothing here can write outside the exports directory.
    """
    data = payload or {}
    name = str(data.get("name") or "export.csv")
    text = str(data.get("text") or "")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name.strip())[:120] or "export.csv"
    folder = _exports_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / Path(safe).name
    target.write_text(text, encoding="utf-8")
    logger.info("export written: %s (%d bytes)", target, len(text))
    return {"ok": True, "path": str(target), "bytes": len(text)}


@router.post("/client-error")
async def client_error(payload: dict = Body(default={})) -> dict[str, Any]:
    """A browser-side exception, with its stack.

    The UI has no console of its own on a frozen build, and the on-screen toast carries only the
    message — so a crash used to be unreadable after the fact. This puts the file:line and the
    stack in the server log, where log tooling (and I) can read it.
    """
    data = payload or {}
    message = str(data.get("message") or "")[:500]
    stack = str(data.get("stack") or "")[:4000]
    source = str(data.get("source") or "")[:200]
    line = data.get("line")
    col = data.get("col")
    # CR/LF are folded out of EVERY field, not just the stack: one client error must stay one
    # log line, or a crafted message forges whole entries (with fake levels/timestamps) in the
    # very file debugging reads.
    message = message.replace(chr(10), ' ').replace(chr(13), ' ')
    source = source.replace(chr(10), ' ').replace(chr(13), ' ')
    line = str(line or "")[:20].replace(chr(10), ' ').replace(chr(13), ' ')
    col = str(col or "")[:20].replace(chr(10), ' ').replace(chr(13), ' ')
    flat = stack.replace(chr(10), ' -> ').replace(chr(13), '')
    logger.error("client error: %s | %s:%s:%s | %s", message, source, line, col, flat)
    return {"ok": True}


@router.get("/workspaces")
async def workspaces_get() -> dict[str, Any]:
    """Every saved layout, straight from the config file (machine-wide, profile-proof)."""
    cfg = config_store.load_config()
    return {"ok": True, "workspaces": cfg.get("workspaces") or {}}


@router.post("/workspaces")
async def workspaces_post(payload: dict = Body(default={})) -> dict[str, Any]:
    """Save, delete or rename a named layout."""
    payload = payload or {}
    cfg = config_store.load_config()
    spaces = cfg.setdefault("workspaces", {})
    if isinstance(payload.get("save"), dict):
        entry = payload["save"]
        name = str(entry.get("name", "") or "").strip()[:32]
        data = entry.get("data") if isinstance(entry.get("data"), dict) else {}
        if not name:
            return {"ok": False, "error": "a workspace needs a name"}
        spaces[name] = data
    if payload.get("delete"):
        spaces.pop(str(payload["delete"])[:32], None)
    if payload.get("rename") and payload.get("to"):
        old_name, new_name = str(payload["rename"])[:32], str(payload["to"])[:32]
        if old_name in spaces and new_name:
            spaces[new_name] = spaces.pop(old_name)
    saved = config_store.save_config(cfg)
    return {"ok": True, "workspaces": saved.get("workspaces") or {}}


# ──────────────────────────────────────────────────────────────
# Terminal layouts — the shell's arrangement store
# (docs/DX_TERMINAL_AND_QUANTOWER_PLAN.md: one store, no second copy in browser storage)
# ──────────────────────────────────────────────────────────────

def _layouts_state(block: dict[str, Any]) -> dict[str, Any]:
    items = block.get("items") if isinstance(block.get("items"), dict) else {}
    return {"mode": block.get("mode") or "classic", "active": block.get("active") or "",
            "items": items, "count": len(items)}


@router.get("/layouts")
async def layouts_get() -> dict[str, Any]:
    """Every saved terminal layout, the boot mode and the active layout (straight from the store)."""
    cfg = config_store.load_config()
    block = cfg.get("layouts") if isinstance(cfg.get("layouts"), dict) else {}
    return {"ok": True, **_layouts_state(block)}


@router.post("/layouts")
async def layouts_post(payload: dict = Body(default={})) -> dict[str, Any]:
    """One write per call: mode · save · import · duplicate · rename · delete · activate · export.

    Actions apply in that order, so `{"save": …, "activate": …}` is a single round trip. The response
    carries the state the store *accepted* — the store's sanitiser is the authority, so a layout it
    refused is reported instead of quietly vanishing, and a caller can never display an arrangement
    the app would not honour.
    """
    payload = payload if isinstance(payload, dict) else {}
    cfg = config_store.load_config()
    block = cfg.get("layouts") if isinstance(cfg.get("layouts"), dict) else {}
    if not isinstance(block.get("items"), dict):
        block["items"] = {}
    cfg["layouts"] = block
    items: dict[str, Any] = block["items"]
    actions: list[str] = []
    refused = ""
    wanted_save = ""

    if payload.get("export"):
        ident = str(payload["export"]).strip().lower()
        entry = items.get(ident)
        if not isinstance(entry, dict):
            return {"ok": False, "action": "export", "error": f"no layout with id {ident!r}",
                    **_layouts_state(block)}
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(entry.get("name") or ident))[:60] or ident
        # the UI hands this straight to /export/save — a bundle is a file the user can keep
        return {"ok": True, "action": "export", "filename": f"layout-{safe}.json",
                "text": json.dumps({"layout": entry}, indent=2), **_layouts_state(block)}

    def _taken() -> set[str]:
        return {str(x.get("name")) for x in items.values() if isinstance(x, dict)}

    def _free_name(base: str) -> str:
        name, n = base, 2
        while name in _taken() and n < 50:
            name, n = f"{base} {n}", n + 1
        return name

    if isinstance(payload.get("mode"), str):
        actions.append("mode")
        block["mode"] = "terminal" if payload["mode"].strip().lower() == "terminal" else "classic"

    if isinstance(payload.get("import"), dict):
        actions.append("import")
        bundle = payload["import"]
        entry = dict(bundle.get("layout") if isinstance(bundle.get("layout"), dict) else bundle)
        entry["id"] = "ly" + uuid.uuid4().hex[:8]            # an import never overwrites one
        entry["name"] = _free_name(str(entry.get("name") or "Imported layout").strip()[:32]
                                   or "Imported layout")
        items[entry["id"]] = entry

    if isinstance(payload.get("save"), dict):
        actions.append("save")
        entry = dict(payload["save"])
        wanted_save = str(entry.get("id") or "").strip().lower()
        if not wanted_save:
            wanted_save = entry["id"] = "ly" + uuid.uuid4().hex[:8]
        items[wanted_save] = entry

    if payload.get("duplicate"):
        src = str(payload["duplicate"]).strip().lower()
        origin = items.get(src)
        if not isinstance(origin, dict):
            refused = f"no layout with id {src!r}"
        else:
            actions.append("duplicate")
            copy = json.loads(json.dumps(origin))
            copy["id"] = "ly" + uuid.uuid4().hex[:8]
            copy["name"] = _free_name(f"{origin.get('name') or 'Layout'} copy"[:32])
            items[copy["id"]] = copy

    if payload.get("rename") and payload.get("to"):
        ident = str(payload["rename"]).strip().lower()
        if isinstance(items.get(ident), dict):
            actions.append("rename")
            items[ident]["name"] = str(payload["to"]).strip()[:40] or items[ident].get("name")

    if payload.get("delete"):
        ident = str(payload["delete"]).strip().lower()
        if ident in items:
            actions.append("delete")
            items.pop(ident, None)
            if block.get("active") == ident:
                block["active"] = ""

    if isinstance(payload.get("activate"), str) and payload["activate"]:
        ident = payload["activate"].strip().lower()
        if ident in items:
            actions.append("activate")
            block["active"] = ident
        else:
            refused = refused or f"no layout with id {ident!r}"

    saved = config_store.save_config(cfg)
    block_out = saved.get("layouts") if isinstance(saved.get("layouts"), dict) else {}
    state = _layouts_state(block_out)
    if wanted_save and wanted_save not in state["items"]:
        return {"ok": False, "action": "save", **_layouts_state(block_out), "actions": actions,
                "error": "the store refused this layout — its id must be a lowercase slug "
                         "(letters, digits, _ or -, starting with a letter or digit)"}
    return {"ok": True, "action": actions[-1] if actions else "read", "actions": actions,
            "error": refused, **_layouts_state(block_out),
            "note": "layouts live in your config file; the browser keeps no copy"}


# ──────────────────────────────────────────────────────────────
# Auxiliary windows (§73) — one widget per native window, per monitor
# ──────────────────────────────────────────────────────────────
#
# The window itself belongs to the launcher (only it owns pywebview); this is the page's side of
# the conversation. `native: false` is a first-class answer, not an error: in a browser or a
# headless session there is no host, and the shell then offers no window controls at all.

def _windows_state() -> dict[str, Any]:
    """The host, the screens it can place a window on, and what is open right now."""
    host = windows_mod.get_host()
    screens: list[dict] = []
    if host is not None:
        try:
            screens = windows_mod.valid_screens(host.screens())
        except Exception:                        # a backend that cannot enumerate must not 500
            logger.debug("screen enumeration failed", exc_info=True)
    labelled = []
    for index, rect in enumerate(screens):
        row = dict(rect)
        row["index"] = index
        row["label"] = windows_mod.screen_label(rect, index, rect.get("scale"))
        labelled.append(row)
    open_ids: list[str] = []
    if host is not None:
        try:
            open_ids = list(host.open_ids())
        except Exception:
            logger.debug("window enumeration failed", exc_info=True)
    return {
        "native": host is not None,
        "host": getattr(host, "kind", "") if host is not None else "",
        "screens": labelled,
        "open": open_ids,
        "windows": windows_mod.records(),
        "max": config_store.WINDOWS_MAX,
    }


@router.get("/windows")
async def windows_get() -> dict[str, Any]:
    """The auxiliary-window state: screens, what is open, and the set a launch restores."""
    return _windows_state()


@router.post("/windows")
async def windows_post(payload: dict = Body(default={})) -> dict[str, Any]:
    """Open / close / focus / pin one auxiliary window.

    Every path answers with the *resulting* state, so the shell adopts what happened rather than
    what it asked for: a refusal with a reason when the cap is reached, the resolved placement
    (screen, x/y, size) for a window that opened, and `native: false` where windows cannot exist.
    """
    action = str(payload.get("action") or "").strip().lower()
    host = windows_mod.get_host()
    if host is None:
        return {"ok": False, "action": action,
                "error": "no native window host in this session — windows need the desktop app",
                **_windows_state()}

    if action == "open":
        record = config_store.clean_window_record({
            "id": str(payload.get("id") or ("w" + uuid.uuid4().hex[:7])),
            "view": str(payload.get("view") or "").strip().lower(),
            "screen_key": payload.get("screen_key"),
            "width": payload.get("width"),
            "height": payload.get("height"),
            "on_top": payload.get("on_top"),
        })
        if record is None:
            return {"ok": False, "action": action,
                    "error": "a window needs a view (a lowercase slug this build has)",
                    **_windows_state()}
        try:
            open_ids = host.open_ids()
        except Exception:
            open_ids = []
        if record["id"] in open_ids:
            # Already open: focus it. Asking a host to create the same window twice would either
            # duplicate it or throw, and neither is what "open this window" means.
            host.focus(record["id"])
            return {"ok": True, "action": "focus", "opened": record, "focused": record["id"],
                    "note": "that window is already open — brought it to the front",
                    **_windows_state()}
        rows = windows_mod.records()
        if len(rows) >= config_store.WINDOWS_MAX and record["id"] not in {r["id"] for r in rows}:
            return {"ok": False, "action": action,
                    "error": "window limit reached (%d) — close one first" % config_store.WINDOWS_MAX,
                    **_windows_state()}
        try:
            screens = host.screens()
        except Exception:
            screens = []
        screen_index = payload.get("screen")
        placement = windows_mod.place_aux(record, screens, count=len(open_ids),
                                          screen_index=screen_index if isinstance(screen_index, int) else None)
        try:
            host.open(placement)                 # the host owns everything native
        except Exception as exc:
            logger.warning("window open failed", exc_info=True)
            return {"ok": False, "action": action,
                    "error": "the window host refused: %s" % exc, **_windows_state()}
        stored = windows_mod.add_record(placement)   # the sanitiser drops screen/screen_label
        placed = next((r for r in stored if r["id"] == placement["id"]), placement)
        return {"ok": True, "action": action, "opened": placed,
                "screen_label": placement.get("screen_label", ""), "windows_set": stored,
                **_windows_state()}

    if action in ("close", "focus", "ontop"):
        wid = str(payload.get("id") or "").strip().lower()
        if not wid:
            return {"ok": False, "action": action, "error": "which window?", **_windows_state()}
        if action == "close":
            try:
                was_open = bool(host.close(wid))
            except Exception:
                logger.debug("window close failed", exc_info=True)
                was_open = False
            existed = any(r["id"] == wid for r in windows_mod.records())
            windows_mod.drop_record(wid)         # closed from either side, it leaves the set
            if not was_open and not existed:
                return {"ok": False, "action": action, "error": "no window with id %r" % wid,
                        **_windows_state()}
            return {"ok": True, "action": action, "closed": wid, **_windows_state()}

        if action == "focus":
            try:
                ok = bool(host.focus(wid))
            except Exception:
                ok = False
            return {"ok": ok, "action": action,
                    "error": "" if ok else "the window host could not focus %r" % wid,
                    **_windows_state()}

        on_top = bool(payload.get("on_top"))
        try:
            ok = bool(host.set_on_top(wid, on_top))
        except Exception:
            ok = False
        if ok:
            windows_mod.set_on_top(wid, on_top)
        return {"ok": ok, "action": action,
                "error": "" if ok else "the window host could not pin %r" % wid,
                **_windows_state()}

    if action == "close_all":
        closed = []
        for wid in list(_windows_state()["open"]):
            try:
                if host.close(wid):
                    closed.append(wid)
            except Exception:
                logger.debug("window close failed for %s", wid, exc_info=True)
            windows_mod.drop_record(wid)
        return {"ok": True, "action": action, "closed": closed, **_windows_state()}

    return {"ok": False, "action": action,
            "error": "unknown action %r (open, close, focus, ontop, close_all)" % action,
            **_windows_state()}
