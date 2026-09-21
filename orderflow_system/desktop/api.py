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
from orderflow_system.desktop import profiles as profiles_mod

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
        "config": config_store.mask_secrets(cfg),   # SEC-09: same mask as /config
        "status": engine_mod.engine.status(),
        "capabilities": engine_mod.capabilities(),
        "system": {
            "platform": sys.platform,
            "platform_name": platform.platform(),
            "python": platform.python_version(),
            "config_path": str(config_store.config_path()),
            "log_path": str(config_store.log_path()),
            "db_path": str(config_store.db_path()),
            "config_error": config_store.config_error(),
        },
    }


@router.get("/config")
async def get_config() -> dict[str, Any]:
    # SEC-09: credentials are write-only — masked here, restored on the way back in by
    # config_store.unmask_patch(). The UI shows the mask, never the stored value.
    return config_store.mask_secrets(config_store.load_config())


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
# Configuration artifacts (T12/B10): the workspace and the studies setup as portable files
# ──────────────────────────────────────────────────────────────

#: What each artifact kind carries. Blocks not listed here never travel.
_ARTIFACT_FORMAT = "ofap-config"
_ARTIFACT_SCHEMA = 1
_ARTIFACT_BLOCKS: dict[str, tuple[str, ...]] = {
    "workspace": ("layouts", "workspaces", "ui"),
    "studies": ("studies", "expression", "atlas", "ofx"),
}


def artifact_build(cfg: dict[str, Any], kind: str) -> dict[str, Any] | None:
    """One portable file\'s worth of `kind`, or None for an unknown kind."""
    blocks = _ARTIFACT_BLOCKS.get(kind)
    if blocks is None:
        return None
    return {
        "format": _ARTIFACT_FORMAT,
        "schema": _ARTIFACT_SCHEMA,
        "kind": kind,
        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "app_version": cfg.get("version"),
        "blocks": {name: cfg.get(name) for name in blocks if name in cfg},
    }


def artifact_validate(raw: Any) -> tuple[dict[str, Any] | None, str]:
    """Read an artifact, or say readably why not. Returns (artifact, "") or (None, reason)."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None, "this file is not JSON - an artifact is a .json export of the program\'s own settings."
    if not isinstance(raw, dict):
        return None, "no artifact found in the request."
    if raw.get("format") != _ARTIFACT_FORMAT:
        return None, "this file is not an OFAP configuration artifact (no format marker)."
    schema = raw.get("schema")
    if not isinstance(schema, int) or schema < 1:
        return None, "the artifact has no readable schema version."
    if schema > _ARTIFACT_SCHEMA:
        return None, f"the artifact was made by a newer build (schema {schema}; this build reads {_ARTIFACT_SCHEMA})."
    kind = raw.get("kind")
    if kind not in _ARTIFACT_BLOCKS:
        return None, f"unknown artifact kind {kind!r} - expected one of: {', '.join(_ARTIFACT_BLOCKS)}."
    blocks = raw.get("blocks")
    if not isinstance(blocks, dict) or not any(name in blocks for name in _ARTIFACT_BLOCKS[kind]):
        return None, "the artifact carries none of the blocks this kind is made of."
    return raw, ""


def artifact_code_modules(artifact: dict[str, Any]) -> list[str]:
    """Names of the custom studies in an artifact that carry JavaScript SOURCE (audit SEC-02).

    A studies artifact is settings-shaped but can hold whole JS modules. Importing one used to
    store that source and the shell compiled it with ``new Function`` on the next load — in the
    app's own origin, where ``GET /config`` hands back the stored credentials. The import asks
    first; without the explicit consent flag the source is dropped.
    """
    studies = (artifact.get("blocks") or {}).get("studies") or {}
    custom = studies.get("custom") if isinstance(studies, dict) else None
    return [str(module.get("name") or f"module {index + 1}")
            for index, module in enumerate(custom or [])
            if isinstance(module, dict) and str(module.get("source") or "").strip()]


def artifact_strip_code(artifact: dict[str, Any]) -> int:
    """Drop every module source from the artifact in place. Returns how many were dropped."""
    studies = (artifact.get("blocks") or {}).get("studies") or {}
    custom = studies.get("custom") if isinstance(studies, dict) else None
    dropped = 0
    for module in custom or []:
        if isinstance(module, dict) and str(module.get("source") or "").strip():
            module["source"] = ""
            dropped += 1
    return dropped


@router.get("/config/artifact")
async def get_config_artifact(kind: str = Query("workspace")) -> dict[str, Any]:
    """T12/B10: the workspace or the studies setup as one portable JSON file."""
    artifact = artifact_build(config_store.load_config(), kind)
    if artifact is None:
        return {"ok": False, "error": f"unknown artifact kind {kind!r} - expected: workspace, studies."}
    return {"ok": True, "artifact": artifact}


@router.post("/config/import")
async def post_config_import(payload: dict = Body(default={})) -> dict[str, Any]:
    """T12/B10: import an artifact - validated first, and a bad file changes nothing."""
    raw = (payload or {}).get("artifact")
    artifact, why = artifact_validate(raw)
    if artifact is None:
        return {"ok": False, "error": why}
    kind = artifact["kind"]
    with_code = artifact_code_modules(artifact)
    allow_code = bool((payload or {}).get("allow_code"))
    dropped = 0
    if with_code and not allow_code:
        # SEC-02: no consent, no code. The names still travel back so the UI can say exactly what
        # was left out, and the user can re-import with the flag after agreeing.
        dropped = artifact_strip_code(artifact)
    cfg = config_store.load_config()
    applied = []
    for name in _ARTIFACT_BLOCKS[kind]:
        if name in artifact["blocks"]:
            cfg[name] = artifact["blocks"][name]
            applied.append(name)
    config_store.save_config(cfg)          # sanitised on the way in; blocks apply whole
    if dropped:
        logger.info("[config] import: dropped %d custom stud%s source(s) without consent",
                    dropped, "y" if dropped == 1 else "ies")
    return {"ok": True, "kind": kind, "schema": artifact["schema"], "applied": applied,
            "code_modules": with_code, "code_stripped": dropped}


@router.get("/config/defaults")
async def config_defaults() -> dict[str, Any]:
    """The factory config, read-only.

    The per-view factory reset (T6/A15) needs to know what the defaults ARE without applying
    them — the reset endpoint above writes, this one only answers.
    """
    return {"ok": True, "config": config_store.default_config()}


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
        caps["ninjatrader"] = await asyncio.to_thread(engine_mod.ninjatrader_status)
        caps["ninjatrader_symbols"] = await asyncio.to_thread(engine_mod.ninjatrader_validate, symbols)
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
    nt = engine_mod.ninjatrader_status()
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
        "ninjatrader": {
            "usable": nt["available"],
            "reason": nt["reason"] or "NinjaTrader bridge ready",
            "symbols": [s for s in symbols
                        if engine_mod.ninjatrader_capable(config_store.instrument_cfg(cfg, s) or {"symbol": s})],
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


#: The config stamp each addable source writes when it confirms a symbol (§82). Bybit was
#: the original path; the Engine panel's look-up uses the same map for MT5 and Alpaca, so a
#: row added from any of them carries the same kind of evidence `select_instruments` reads.
ADD_STAMP_KEYS = {
    "bybit": "bybit_symbol",
    "binance": "binance_symbol",
    "hyperliquid": "hyperliquid_symbol",
    "okx": "okx_symbol",
    "mt5": "mt5_symbol",
    "alpaca": "alpaca_symbol",
    "ninjatrader": "ninjatrader_symbol",
}

#: The accepted single-venue sources, in the order the panel should prefer them when the
#: active source is a combined one ("both" = bybit+mt5, "all" = everything).
_ADDABLE_SOURCES = ("bybit", "binance", "hyperliquid", "okx", "mt5", "alpaca", "ninjatrader")


def _add_source(payload_source: str, cfg: dict[str, Any], symbols: list[str]) -> str:
    """Which venue the add is against: the caller's choice, else the active source, else bybit.

    A combined active source cannot be an add target on its own — the residue is decided by
    what the symbol looks like (a USDT pair is the exchange lane, anything else the broker).
    """
    wanted = str(payload_source or "").strip().lower()
    if wanted in _ADDABLE_SOURCES:
        return wanted
    active = str(cfg.get("data_source") or "").strip().lower()
    if active in _ADDABLE_SOURCES:
        return active
    if active == "both":
        return "bybit" if symbols and all(s.endswith("USDT") for s in symbols) else "mt5"
    if active == "all":
        # `all` runs the broker leg too (it used to run Alpaca alone), so a non-exchange residue
        # goes where the partition sends it: the broker, which resolves names and refuses honestly.
        return "bybit" if symbols and all(s.endswith("USDT") for s in symbols) else "mt5"
    return "bybit"


@router.post("/instruments/add")
async def instruments_add(payload: dict = Body(default={})) -> dict[str, Any]:
    """Add venue-confirmed instruments to the config, tick sizes straight from the venue.

    A fresh install ships one crypto instrument; the setup assistant offers the rest this way.
    §82 gave the route two more lanes and one rule: the caller may name the source, the row is
    stamped only on evidence the venue itself gave (a Bybit catalogue hit, an MT5
    ``symbol_info``, an Alpaca mapping), and a symbol nothing confirms is reported in
    ``skipped`` rather than written into the config.
    """
    import json

    wanted = [str(s).upper().strip() for s in (payload.get("symbols") or []) if str(s).strip()]
    if not wanted:
        return {"ok": False, "error": "no symbols given", "added": [], "updated": [], "skipped": []}
    cfg = config_store.load_config()
    source = _add_source(str(payload.get("source") or ""), cfg, wanted)
    stamp_key = ADD_STAMP_KEYS.get(source, "bybit_symbol")
    ticks = {str(k).upper(): v for k, v in dict(payload.get("ticks") or {}).items()}
    mt5_names = {str(k).upper(): str(v).strip() for k, v in dict(payload.get("mt5_symbols") or {}).items()}
    enable = bool(payload.get("enable"))
    asset_class = str(payload.get("asset_class") or "").strip()

    catalog: dict[str, dict[str, Any]] = {}
    broker: dict[str, dict[str, Any]] = {}
    reasons: dict[str, str] = {}
    if source == "bybit":
        try:
            catalog = await asyncio.to_thread(_fetch_venue_catalog)
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "source": source,
                    "added": [], "updated": [], "skipped": []}
    elif source == "mt5":
        if sys.platform != "win32":
            return {"ok": False, "source": source, "added": [], "updated": [], "skipped": [],
                    "error": "the MT5 feed is Windows-only"}
        names = [mt5_names.get(sym) or sym for sym in wanted]
        check = await asyncio.to_thread(engine_mod.mt5_validate_symbols, names, dict(cfg.get("mt5") or {}))
        if not check.get("ok"):
            return {"ok": False, "source": source, "added": [], "updated": [], "skipped": [],
                    "error": str(check.get("reason") or "MT5 is not available")}
        broker = dict(check.get("symbols") or {})
        for sym in wanted:
            stamp = mt5_names.get(sym) or sym
            if not (broker.get(stamp) or {}).get("listed"):
                reasons[sym] = f"the broker does not list {stamp}"
    elif source == "alpaca":
        from orderflow_system.desktop import alpaca as alpaca_mod

        alp = dict(cfg.get("alpaca") or {})
        if not (alp.get("key_id") and alp.get("secret")):
            return {"ok": False, "source": source, "added": [], "updated": [], "skipped": [],
                    "error": "link an Alpaca account first (Alpaca view) — the asset list needs the keys"}
        alpaca_symbols = {str(k).upper(): str(v).strip() for k, v in dict(payload.get("alpaca_symbols") or {}).items()}
        client = alpaca_mod.AlpacaClient(alp.get("key_id", ""), alp.get("secret", ""), bool(alp.get("paper", True)))

        def _active_assets() -> Optional[dict[str, Any]]:
            status_code, body = client.assets()
            if status_code != 200 or not isinstance(body, list):
                return None
            return {str(a.get("symbol") or "").upper(): a for a in body
                    if a.get("symbol") and a.get("tradable", True)}

        assets = await asyncio.to_thread(_active_assets)
        if assets is None:
            return {"ok": False, "source": source, "added": [], "updated": [], "skipped": [],
                    "error": "Alpaca's asset list could not be read — check the keys and paper mode"}
        for sym in wanted:
            target = (alpaca_symbols.get(sym) or sym).upper()
            if target not in assets:
                reasons[sym] = f"Alpaca does not list {target}"
                continue
            broker[sym] = {"listed": True, "tick_size": 0.01, "alpaca": target}
    elif source == "ninjatrader":
        check = await asyncio.to_thread(engine_mod.ninjatrader_validate, wanted)
        if not check.get("ok"):
            return {"ok": False, "source": source, "added": [], "updated": [], "skipped": [],
                    "error": str(check.get("reason") or "the NinjaTrader bridge is not available")}
        for sym in wanted:
            info = (check.get("symbols") or {}).get(sym) or {}
            if info.get("listed"):
                broker[sym] = {"listed": True, "tick_size": info.get("tick_size"),
                               "ninjatrader": info.get("ninjatrader") or sym}
            else:
                reasons[sym] = f"your NinjaTrader terminal does not list {sym}"
    elif source in ("binance", "hyperliquid", "okx"):
        validate = {"binance": engine_mod.binance_validate, "hyperliquid": engine_mod.hyperliquid_validate,
                    "okx": engine_mod.okx_validate}[source]
        try:
            listed = await asyncio.to_thread(validate, wanted)
        except Exception as exc:
            return {"ok": False, "source": source, "added": [], "updated": [], "skipped": [],
                    "error": f"{type(exc).__name__}: {exc}"}
        for sym in wanted:
            if listed.get(sym):
                broker[sym] = {"listed": True, "tick_size": ticks.get(sym)}
            else:
                reasons[sym] = f"{source} does not list it"

    instruments = cfg.get("instruments") or []
    by_symbol = {i["symbol"]: i for i in instruments}
    template = by_symbol.get("BTCUSDT") or (instruments[0] if instruments else {})
    added: list[str] = []
    updated: list[str] = []
    skipped: list[dict[str, str]] = []

    for sym in wanted:
        tick = ticks.get(sym)
        stamp = sym
        if source == "bybit":
            info = catalog.get(sym)
            if info is None or info.get("status") not in ("Trading", ""):
                skipped.append({"symbol": sym, "reason": "the venue does not list it"})
                continue
            tick = tick if tick is not None else info.get("tick_size")
        elif source == "mt5":
            stamp = mt5_names.get(sym) or sym
            info = broker.get(stamp) or {}
            if not info.get("listed"):
                skipped.append({"symbol": sym, "reason": reasons.get(sym) or f"the broker does not list {stamp}"})
                continue
            tick = tick if tick is not None else (info.get("tick_size") or None)
        else:                                    # alpaca / the venue-validate lanes
            info = broker.get(sym) or {}
            if not info.get("listed"):
                skipped.append({"symbol": sym, "reason": reasons.get(sym) or f"the venue does not list it ({source})"})
                continue
            if source == "alpaca":
                stamp = str(info.get("alpaca") or sym)
            elif source == "ninjatrader":
                stamp = str(info.get("ninjatrader") or sym)
            else:
                stamp = sym
            tick = tick if tick is not None else info.get("tick_size")

        row = by_symbol.get(sym)
        if row is not None:
            row[stamp_key] = stamp
            if tick is not None:
                row["tick_size"] = float(tick)
            updated.append(sym)
            continue
        entry = {
            "symbol": sym,
            "asset_class": asset_class or config_store.ASSET_CLASS.get(sym, "Other"),
            "enabled": enable,
            "mt5_symbol": stamp if source == "mt5" else "",
            "alpaca_symbol": stamp if source == "alpaca" else "",
            "bybit_symbol": stamp if source == "bybit" else "",
            "ninjatrader_symbol": stamp if source == "ninjatrader" else "",
            "tick_size": float(tick) if tick is not None else 0.01,
            "patterns": json.loads(json.dumps(template.get("patterns") or {})),
        }
        if stamp_key not in entry:               # binance/hyperliquid/okx stamps ride in as-is
            entry[stamp_key] = stamp
        instruments.append(entry)
        by_symbol[sym] = entry
        added.append(sym)

    if enable:
        for sym in added + updated:
            by_symbol[sym]["enabled"] = True

    saved = config_store.save_config(cfg)
    return {"ok": True, "source": source, "added": added, "updated": updated, "skipped": skipped,
            "config": saved}


#: The linked Alpaca account's tradable symbols (SPY, QQQ, …), read through the palette's shared
#: AlpacaData — disk-cached a day there — behind a short in-process TTL so a keystroke-driven
#: resolve never waits on the disk. §82-ext: the look-up's Alpaca lane and the resolver both read
#: the venue's own list, the same way MT5 reads the broker's symbol_info.
_ALPACA_SYMBOLS_CACHE: dict[str, Any] = {"at": 0.0, "symbols": [], "by_norm": {}}
_ALPACA_SYMBOLS_TTL_S = 600.0


def _alpaca_asset_symbols() -> list[str]:
    """Tradable US symbols of the linked account; [] when unlinked or unreadable — never raises."""
    import time as _time

    now = _time.time()
    cached = list(_ALPACA_SYMBOLS_CACHE.get("symbols") or [])
    if cached and (now - float(_ALPACA_SYMBOLS_CACHE.get("at") or 0.0)) < _ALPACA_SYMBOLS_TTL_S:
        return cached
    try:
        rows = _search_data().assets() or []
    except Exception:                      # noqa: BLE001 — the look-up must answer regardless
        rows = []
    symbols = [str(r.get("symbol") or "").strip().upper() for r in rows
               if isinstance(r, dict) and str(r.get("symbol") or "").strip()]
    # MEM-B-09: the normalised index is built once per refresh, with the list — the resolver
    # used to rebuild it per keystroke.
    from orderflow_system.desktop.instrument_lookup import normalise as _normalise

    by_norm = {_normalise(s): s for s in symbols if _normalise(s)}
    _ALPACA_SYMBOLS_CACHE["symbols"], _ALPACA_SYMBOLS_CACHE["by_norm"] = symbols, by_norm
    _ALPACA_SYMBOLS_CACHE["at"] = now
    return list(symbols)


def _alpaca_asset_index() -> dict[str, str]:
    """The cached {normalise(symbol): symbol} index (MEM-B-09); {} when unlinked."""
    _alpaca_asset_symbols()                    # refreshes the cache when stale
    return dict(_ALPACA_SYMBOLS_CACHE.get("by_norm") or {})


def _resolve_instrument(symbol: str, cfg: dict[str, Any] | None = None,
                        *, broker_names: Optional[list[str]] = None,
                        nt_names: Optional[list[str]] = None,
                        alpaca_names: Optional[list[str]] = None,
                        alpaca_by_norm: Optional[dict[str, str]] = None) -> dict[str, Any]:
    """One builder for the instrument look-up's answer (§82) — every caller gets the same one.

    ``broker_names`` / ``nt_names`` are the venue symbol lists (MT5's broker list, the
    NinjaTrader terminal's instrument list) when the caller could afford to fetch them;
    without them the look-up still answers from the config and the engine alone (and says so).
    """
    from orderflow_system.desktop import instrument_lookup

    cfg = cfg if cfg is not None else config_store.load_config()
    status = engine_mod.engine.status()
    mt5 = engine_mod.mt5_status() or {}
    return instrument_lookup.resolve(
        symbol,
        instruments=list(cfg.get("instruments") or []),
        engine_symbols=list(status.get("symbols") or []),
        source=str(cfg.get("data_source") or "bybit"),
        running=bool(status.get("running")),
        mt5_available=bool(mt5.get("available")),
        mt5_known=list(broker_names or []),
        nt_known=list(nt_names or []),
        alpaca_known=list(alpaca_names or []),
        # only a *populated* prebuilt index is passed — an empty one must never shadow the
        # names the caller did supply (MEM-B-09)
        alpaca_by_norm=alpaca_by_norm or None,
    )


@router.get("/instruments/resolve")
async def instruments_resolve(symbol: str = "", broker: bool = True) -> dict[str, Any]:
    """What a typed symbol is: live, ready, disabled, addable or unknown — plus why (§82).

    The Engine view's symbol box calls this before it accepts a change, so a name nothing
    can stream is answered with a reason and an action instead of a blank stage.
    """
    cfg = config_store.load_config()
    names: list[str] = []
    nt_names: list[str] = []
    source = str(cfg.get("data_source") or "").lower()
    if broker and source in ("mt5", "both", "all"):
        found = await asyncio.to_thread(engine_mod.mt5_symbol_names, dict(cfg.get("mt5") or {}))
        names = list(found.get("names") or [])
    elif broker and source == "ninjatrader":
        rows = await asyncio.to_thread(engine_mod.ninjatrader_symbol_names)
        nt_names = [str(row.get("Name") or "") for row in rows
                    if isinstance(row, dict) and row.get("Name")]
    alpaca_names: list[str] = []
    alpaca_index: dict[str, str] = {}
    alp = dict(cfg.get("alpaca") or {})
    if alp.get("key_id") and alp.get("secret"):
        alpaca_names = await asyncio.to_thread(_alpaca_asset_symbols)
        alpaca_index = await asyncio.to_thread(_alpaca_asset_index)     # MEM-B-09: prebuilt
    out = _resolve_instrument(symbol, cfg, broker_names=names, nt_names=nt_names,
                              alpaca_names=alpaca_names, alpaca_by_norm=alpaca_index)
    total = len(nt_names) if source == "ninjatrader" else len(names)
    return {"ok": True, **out, "source": source or "bybit",
            "broker_total": total, "running": bool(engine_mod.engine.status().get("running"))}


@router.get("/mt5/symbols")
async def mt5_symbol_list(q: str = "", limit: int = 40) -> dict[str, Any]:
    """Search the connected broker's own symbol list (the wizard's "which name is it?").

    Served from the feed module's cached listing; a terminal that is missing or not logged
    in comes back as ``ok: false`` with the reason, never as an empty list.
    """
    cfg = config_store.load_config()
    payload = dict(cfg.get("mt5") or {})
    try:
        want = max(1, min(200, int(limit)))
    except (TypeError, ValueError):
        want = 40
    return await asyncio.to_thread(engine_mod.mt5_symbols, payload, str(q or ""), want)


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
    """Save the active studies, add/replace a pasted module, or manage a saved set."""
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
    # §117: saved sets — "save" snapshots the current (or posted) active list under a name,
    # "apply" swaps the named set into the live list, "delete" forgets it. One write per call.
    coll = payload.get("collection")
    if isinstance(coll, dict):
        action = str(coll.get("action") or "").strip().lower()
        name = str(coll.get("name") or "").strip()[:32]
        collections = studies.get("collections") if isinstance(studies.get("collections"), dict) else {}
        if action == "save" and name:
            source = coll.get("active") if isinstance(coll.get("active"), list) else (studies.get("active") or [])
            collections[name] = {"saved": int(time.time() * 1000), "active": source}
        elif action == "apply" and name in collections:
            studies["active"] = list(collections[name].get("active") or [])
        elif action == "delete" and name:
            collections.pop(name, None)
        else:
            return {"ok": False, "error": "unknown collection action: " + (action or "(none)")}
        studies["collections"] = collections
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
# offered as a switch that would silently fall back to bybit. Each hint also names what the
# venue CARRIES — the Data menu shows it on hover, and the "where do I get index funds?" hunt
# is answered in place by the explainer row beside it.
FREE_SOURCES = (
    ("bybit", "Bybit", "public WS + REST — trades, order book depth, candles, no key · crypto only — indices need Alpaca, MT5 or NinjaTrader",
     "https://api.bybit.com/v5/market/time", True),
    ("binance", "Binance Futures", "public WS + REST — trades, 100–1000-level book, candles, no key · crypto only — indices need Alpaca, MT5 or NinjaTrader",
     "https://fapi.binance.com/fapi/v1/time", True),
    ("mt5", "MetaTrader 5", "your local terminal — free if it is installed here · index CFDs, FX, metals via your broker", "", True),
    ("alpaca", "Alpaca crypto", "keyless crypto quotes and bars (no book) · keys add US stocks, ETFs and options",
     "https://data.alpaca.markets/v1beta3/crypto/us/latest/quotes?symbols=BTC%2FUSD", True),
    ("okx", "OKX", "public WS + REST — trades, 400-level book, no key · crypto only — indices need Alpaca, MT5 or NinjaTrader",
     "https://www.okx.com/api/v5/public/time", True),
    ("hyperliquid", "Hyperliquid", "public WS + REST — trades, whole-book snapshots, no key · crypto only — indices need Alpaca, MT5 or NinjaTrader",
     "https://api.hyperliquid.xyz/info", True),
    ("ninjatrader", "NinjaTrader 8", "your local terminal — free demo accounts work; needs the bridge add-on once · index futures (ES, NQ) and more",
     "tcp://127.0.0.1:8790", True),
)

#: POST-only probe bodies: Hyperliquid's `/info` answers a bare GET with 405, so a plain GET probe
#: would paint the venue "unreachable" while it is healthy. The probe then sends what the adapter
#: itself sends (one `meta` call).
_PROBE_PAYLOADS = {"hyperliquid": {"type": "meta"}}


def _probe_source(url: str, timeout: float = 4.0, payload: Optional[dict] = None) -> str:
    """ok / unreachable / installed / idle — a reachability fact, never a guess about capability.

    ``payload`` is for POST-only endpoints (see `_PROBE_PAYLOADS`): the probe then makes the same
    request the adapter makes, instead of a GET the venue answers with 405. A ``tcp://`` URL is a
    loopback service (the NinjaTrader bridge): the probe is one connect, and "idle" means the
    platform is not running — say so, never "unreachable".
    """
    if url.startswith("tcp://"):
        import socket
        try:
            hostport = url[len("tcp://"):]
            host, _, port_text = hostport.partition(":")
            with socket.create_connection((host, int(port_text or "0")), timeout=min(timeout, 1.0)):
                return "ok"
        except (OSError, ValueError):
            return "idle"
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


#: The /sources sweep: seven blocking socket probes (up to ~4 s each), so the result is cached
#: and the sweep runs on a worker thread instead of the feeds' event loop (measured uncached:
#: 2.7 s per call). `?refresh=1` forces a fresh sweep.
_SOURCES_CACHE: dict[str, Any] = {"at": 0.0, "rows": None}
_SOURCES_TTL_S = 20.0


def _probe_all_sources() -> list[dict[str, Any]]:
    return [{"id": sid, "name": name, "hint": hint,
             "status": _probe_source(url, payload=_PROBE_PAYLOADS.get(sid)), "wired": wired}
            for sid, name, hint, url, wired in FREE_SOURCES]


@router.get("/sources")
async def sources(refresh: int = Query(default=0)) -> dict[str, Any]:
    """Every data source that costs nothing, with a live reachability read and the active one."""
    import time as _time

    now = _time.time()
    rows = _SOURCES_CACHE["rows"]
    if refresh or rows is None or (now - float(_SOURCES_CACHE["at"])) >= _SOURCES_TTL_S:
        rows = await asyncio.to_thread(_probe_all_sources)
        _SOURCES_CACHE["rows"], _SOURCES_CACHE["at"] = rows, now
    cfg = config_store.load_config()
    active = str(cfg.get("data_source") or "bybit")
    return {"ok": True, "sources": [dict(r) for r in rows], "active": active,
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
        elif param.kind == "list":
            # The list kind (numbers): an array or a comma-separated string; finite values only,
            # never empty — the store clamps afterwards like every other write.
            items = raw if isinstance(raw, list) else str(raw).split(",")
            value = []
            for item in items:
                try:
                    num = float(str(item).strip())
                except (TypeError, ValueError):
                    continue
                if num == num and abs(num) < 1e12:
                    value.append(num)
            if not value:
                return {"ok": False, "error": "the list needs at least one number"}
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
    # §122: save-then-apply for the Depth-heat dials — the RUNNING hub re-tunes from the saved
    # atlas block, so bucket width, ceilings, floors and schemes take effect without a restart
    # (the registry's restart notes stay as the conservative fallback wording).
    if path.startswith("atlas."):
        try:
            from orderflow_system.desktop import engine as engine_mod
            system = engine_mod.engine.system
            hub = getattr(system, "_atlas_hub", None)
            if hub is not None:
                hub.configure(saved.get("atlas") or {})
        except Exception:
            pass   # engine not running: the next start reads the same config anyway
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
        "backups": _backups_dir(),          # R6: wherever the user pointed the backup job
        "archive": config_store.config_path().parent / "archive",   # the quarantine folder
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
    the renderer unusable.

    The answer carries the look-up's verdict on the stored symbol (§82): the panel used to
    save any string and quietly fetch nothing, so the *save* is where the reason belongs.
    """
    cfg = config_store.load_config()
    ofx = cfg.setdefault("ofx", {})
    for key in ("symbol", "R", "stack", "lambda_ms", "text_px", "sweep_c", "min_block", "va_pct", "ramp"):
        if key in payload:
            ofx[key] = payload[key]
    saved = config_store.save_config(cfg)
    symbol = str((saved.get("ofx") or {}).get("symbol") or "")
    stream = (_resolve_instrument(symbol, saved) if symbol
              else {"symbol": "", "state": "unknown", "reason": "type an instrument name",
                    "actions": ["open_instruments"], "via": None, "instrument": None, "suggestions": []})
    return {"ok": True, "ofx": saved.get("ofx") or {}, "stream": stream,
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


def _ninjatrader_block(cfg: dict[str, Any]) -> dict[str, Any]:
    """The stored NinjaTrader bridge settings, coerced to the shape the UI expects.

    There is nothing secret in here: the bridge is a loopback socket to an add-on that was
    installed by hand, so the block is a host, a port, a symbol and the plan the user runs.
    """
    from orderflow_system.desktop import platforms as platform_mod
    stored = ((cfg.get("platforms") or {}).get("ninjatrader") or {})
    return {**platform_mod.ninjatrader_defaults(), **(stored if isinstance(stored, dict) else {})}


def _mask_ninjatrader(block: dict[str, Any]) -> dict[str, Any]:
    """Same shape out, with the plan validated against the published plans."""
    from orderflow_system.desktop import platforms as platform_mod
    safe = dict(block)
    safe["plan"] = safe.get("plan") if safe.get("plan") in platform_mod.NINJATRADER_PLAN_IDS else "free"
    safe["host"] = str(safe.get("host") or "127.0.0.1")
    safe["protocol"] = platform_mod.ninjatrader_defaults()["protocol"]
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
    nt_block = _ninjatrader_block(cfg)
    cat = platform_mod.catalogue()
    rows = {row.get("id"): row for row in (cat.get("platforms") or [])}
    platform_row = rows.get("sierra") or (cat.get("platforms") or [{}])[0]
    bookmap_row = rows.get("bookmap") or {}
    nt_row = rows.get("ninjatrader") or {}
    installs = await asyncio.to_thread(platform_mod.detect_installs)
    return {
        "ok": True,
        "sierra": _mask_dtc(block),
        "bookmap": _mask_bookmap(bookmap_block),
        "ninjatrader": _mask_ninjatrader(nt_block),
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
        "ninjatrader_plans": nt_row.get("plans", []),
        "ninjatrader_links": nt_row.get("links", []),
        "ninjatrader_prices_as_of": nt_row.get("prices_as_of", ""),
        "ninjatrader_caveats": nt_row.get("caveats", []),
        "ninjatrader_limits": nt_row.get("limits", {}),
        "ninjatrader_workflow": platform_mod.ninjatrader_workflow(nt_block.get("plan", "free")),
        "ninjatrader_bridge": platform_mod.ninjatrader_bridge_state(),
        "installs": installs,
        "suggested_symbols": platform_mod.suggested_symbols(config_store.enabled_symbols(cfg)),
        "free_note": "The free trial and the delayed streaming feed need no payment — start there.",
        "bookmap_free_note": "Bookmap's free tier (Digital) needs an account and no payment: crypto "
                             "depth, one instrument at a time, 1 hour of backfill.",
        "note": "Optional: a DTC server on your own platform can feed this suite directly.",
        "bookmap_note": "Optional: Bookmap has no data-out API, so this suite ships a small read-only "
                        "add-on that republishes its live trades and depth on loopback.",
        "ninjatrader_free_note": "The free path is real: the Simulated Data Feed needs no payment and "
                                 "Kinetick End-Of-Day is free — real-time CME/EUREX Level I comes with a "
                                 "funded NinjaTrader brokerage account.",
        "ninjatrader_note": "Optional and powerful: NinjaTrader has no market-data-out API, so this "
                            "suite ships a small read-only bridge add-on — and the terminal also "
                            "becomes a full engine data source (add NQ/ES/… from its own list).",
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
    ninjatrader = which == "ninjatrader"
    bookmap = which == "bookmap"
    ids = (platform_mod.NINJATRADER_PLAN_IDS if ninjatrader
           else platform_mod.BOOKMAP_PLAN_IDS if bookmap else platform_mod.PLAN_IDS)
    fallback = "free" if ninjatrader else "digital" if bookmap else "free"
    block = cfg.setdefault("platforms", {}).setdefault(
        "ninjatrader" if ninjatrader else "bookmap" if bookmap else "sierra", {})
    if "plan" in payload:
        plan = str(payload.get("plan") or fallback).lower()
        block["plan"] = plan if plan in ids else fallback
    if "integrated" in payload:
        block["integrated"] = bool(payload["integrated"])
    saved = config_store.save_config(cfg)
    dtc = _dtc_block(saved)
    bm = _bookmap_block(saved)
    nt = _ninjatrader_block(saved)
    return {
        "ok": True,
        "platform": "ninjatrader" if ninjatrader else "bookmap" if bookmap else "sierra",
        "sierra": _mask_dtc(dtc),
        "bookmap": _mask_bookmap(bm),
        "ninjatrader": _mask_ninjatrader(nt),
        "plans": (platform_mod.NINJATRADER_PLANS if ninjatrader
                  else platform_mod.BOOKMAP_PLANS if bookmap else platform_mod.PLANS),
        "workflow": (platform_mod.ninjatrader_workflow(nt.get("plan", "free")) if ninjatrader
                     else platform_mod.bookmap_workflow(bm.get("plan", "digital")) if bookmap
                     else platform_mod.workflow(dtc.get("plan", "free"))),
        "price_note": f"prices read {platform_mod.NINJATRADER_PRICES_AS_OF if ninjatrader else platform_mod.BOOKMAP_PRICES_AS_OF if bookmap else platform_mod.PRICES_AS_OF}"
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


@router.post("/platforms/bridge/ninjatrader")
async def ninjatrader_settings_save(payload: dict = Body(default={})) -> dict[str, Any]:
    """Save the NinjaTrader bridge settings. No credentials exist here: it is a loopback socket.

    The bridge add-on is the server; the suite only ever connects to the host/port it bound.
    """
    from orderflow_system.desktop import platforms as platform_mod

    cfg = config_store.load_config()
    block = _ninjatrader_block(cfg)
    for key in ("enabled", "host", "symbol", "integrated", "bridge_built"):
        if key in payload and payload[key] is not None:
            block[key] = payload[key]
    if payload.get("port") is not None:
        try:
            port = int(payload["port"])
        except (TypeError, ValueError):
            port = block.get("port", 8790)
        block["port"] = port if 1 <= port <= 65535 else 8790
    if payload.get("plan") is not None:
        plan = str(payload["plan"]).lower()
        block["plan"] = plan if plan in platform_mod.NINJATRADER_PLAN_IDS else "free"
    block["protocol"] = platform_mod.ninjatrader_defaults()["protocol"]
    cfg.setdefault("platforms", {})["ninjatrader"] = block
    saved = config_store.save_config(cfg)
    return {"ok": True, "ninjatrader": _mask_ninjatrader(_ninjatrader_block(saved)),
            "note": "Stored in your per-user config file; the bridge only ever dials 127.0.0.1."}


@router.post("/platforms/bridge/ninjatrader/test")
async def ninjatrader_test(payload: dict = Body(default={})) -> dict[str, Any]:
    """Connect to the bridge add-on and report what it is streaming — the one-click check.

    Uses the stored settings unless the caller supplies overrides. The answer names the add-on,
    the NinjaTrader build and live connection it reported, message counts, one sample row and
    whether level-2 depth actually arrived; nothing is stored and nothing is sent back.
    """
    from orderflow_system.data.ninjatrader_feed import ninjatrader_probe

    cfg = config_store.load_config()
    block = _ninjatrader_block(cfg)
    host = str(payload.get("host") or block.get("host") or "127.0.0.1")
    try:
        port = int(payload.get("port") or block.get("port") or 8790)
    except (TypeError, ValueError):
        port = 8790
    symbol = str(payload.get("symbol") or block.get("symbol") or "NQ")
    try:
        seconds = min(10.0, max(0.5, float(payload.get("seconds", 3.0) or 3.0)))
    except (TypeError, ValueError):
        seconds = 3.0
    return await asyncio.to_thread(ninjatrader_probe, host, port, seconds=seconds,
                                   timeout=6.0, symbol=symbol)


@router.get("/platforms/bridge/ninjatrader/dll")
async def ninjatrader_dll() -> dict[str, Any]:
    """The bridge DLL this install ships: where it is, whether a copy is installed into
    NinjaTrader's AddOns folder, and whether the two are the same build. Read-only — it never
    loads or runs the DLL."""
    from orderflow_system.desktop import platforms as platform_mod

    return {"ok": True, **platform_mod.ninjatrader_bridge_state()}


@router.post("/platforms/bridge/ninjatrader/dll/open")
async def ninjatrader_dll_open(payload: dict = Body(default={})) -> dict[str, Any]:
    """Open the bridge folder so the DLL can be copied into NinjaTrader.

    Accepts no path from the caller except this suite's own folder (the helper re-checks it).
    """
    from orderflow_system.desktop import platforms as platform_mod

    folder = str(payload.get("folder") or "") or None
    return await asyncio.to_thread(platform_mod.reveal_bridge_dll, folder)

# ──────────────────────────────────────────────────────────────
# Engine control
# ──────────────────────────────────────────────────────────────

@router.get("/marketwatch")
async def marketwatch(source: str = "", filter: str = "", limit: int = 60,
                      offset: int = 0) -> dict[str, Any]:
    """The source's own symbol board (§87) — the platform's Market Watch, fed by this install.

    Bybit answers for the whole board from one cached REST snapshot; MT5 answers per page off
    the terminal; the NinjaTrader branch lists the terminal's master instruments (its bridge
    only republishes subscribed ones, and the note says so). Read-only, loopback where possible.
    """
    from orderflow_system.desktop import marketwatch as marketwatch_mod

    cfg = config_store.load_config()
    return await asyncio.to_thread(
        marketwatch_mod.market_watch,
        source or str(cfg.get("data_source") or "bybit"), filter, limit, offset)


@router.post("/launch")
async def launch_mode(payload: dict = Body(default={})) -> dict[str, Any]:
    """Start one of the program's other run modes in its own console window (§87).

    The top bar's Run menu sends {"mode": "headless" | "cli"}. Headless refuses while port 8099
    already answers; the CLI pipeline exists in the source tree only (it is refused honestly on
    a frozen build). Both share this profile's history store — the response says so, because a
    second writer is exactly how the engine ends up answering *database is locked*.
    """
    import socket
    import subprocess
    import sys
    from pathlib import Path as _Path

    mode = str(payload.get("mode") or "").strip().lower()
    if mode not in ("headless", "cli"):
        return {"ok": False, "error": "unknown mode — 'headless' or 'cli'"}
    frozen = bool(getattr(sys, "frozen", False))
    if mode == "cli" and frozen:
        return {"ok": False, "error": "the CLI pipeline ships in the source tree only — run it "
                                      "there (python -m orderflow_system.main)"}
    if mode == "headless":
        try:
            with socket.create_connection(("127.0.0.1", 8099), timeout=0.4):
                return {"ok": False, "error": "port 8099 is already answering — a headless run is up"}
        except OSError:
            pass
        args = ([sys.executable, "--headless", "--port", "8099"] if frozen
                else [sys.executable, "-m", "orderflow_system.desktop", "--headless", "--port", "8099"])
    else:
        args = [sys.executable, "-m", "orderflow_system.main"]
    repo_root = _Path(__file__).resolve().parents[2]
    try:
        proc = subprocess.Popen(args, cwd=str(repo_root),
                                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    except OSError as exc:
        return {"ok": False, "error": f"launch failed: {exc}"}
    note = ("a headless server is starting in its own console on http://127.0.0.1:8099 — it shares "
            "this profile's history store, so stop it when the smoke test is done"
            if mode == "headless" else
            "the CLI pipeline is starting in its own console (feeds → detectors → Telegram) — it "
            "shares this profile's history store; Ctrl+C in that console stops it")
    return {"ok": True, "mode": mode, "pid": proc.pid, "command": " ".join(args), "note": note}


@router.get("/systems")
async def systems() -> dict[str, Any]:
    """The Systems board (§86): every ingest path + capability with its honest state.

    Read-only aggregation of what the engine and the platform detectors already know — the
    Overview card polls it; nothing here starts or touches anything.
    """
    return await asyncio.to_thread(engine_mod.systems_report)


@router.get("/engine/status")
async def engine_status() -> dict[str, Any]:
    # `profile_restart_pending` rides this payload because this is the poll the whole shell already
    # watches: the feed/instruments/atlas/ofx parts a switch cannot apply to a running engine are
    # reported once, here, instead of every panel asking separately. None when the engine is up to
    # date (or stopped).
    return {**engine_mod.engine.status(),
            "profile_restart_pending": profiles_mod.pending_restart()}


@router.get("/live-status")
async def live_status() -> dict[str, Any]:
    """Per-endpoint live / warming / demo map — the UI's single source of truth.

    The dashboard's "data:" chip reads this; panels that can still serve demo data
    (tape, footprint, microstructure, …) should never guess their own state.
    """
    return engine_mod.engine.live_status()


@router.post("/engine/start")
async def engine_start(cfg: Optional[dict] = Body(default=None)) -> dict[str, Any]:
    # §83: a body here patches the stored config (merge) rather than replacing it — the
    # wizard and the toolbar post a full config, and a future partial caller must not be able
    # to reset the settings the body does not mention.
    if cfg:
        config_store.merge_config(cfg)
    cfg = config_store.load_config()
    logs.install(cfg.get("logging", {}).get("level", "INFO"))
    return await engine_mod.engine.start(cfg)


@router.post("/engine/stop")
async def engine_stop() -> dict[str, Any]:
    return await engine_mod.engine.stop()


@router.post("/engine/restart")
async def engine_restart(cfg: Optional[dict] = Body(default=None)) -> dict[str, Any]:
    if cfg:
        config_store.merge_config(cfg)
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


@router.get("/alpaca/assets")
async def alpaca_assets() -> dict[str, Any]:
    """The linked account's tradable symbols — the look-up's Alpaca lane reads this (§82-ext)."""
    cfg = config_store.load_config()
    alp = dict(cfg.get("alpaca") or {})
    if not (alp.get("key_id") and alp.get("secret")):
        return {"ok": True, "linked": False, "symbols": [], "total": 0,
                "note": "no Alpaca account is linked — the Alpaca view holds the keys"}
    symbols = await asyncio.to_thread(_alpaca_asset_symbols)
    return {"ok": True, "linked": True, "symbols": symbols, "total": len(symbols),
            "note": "" if symbols else "the asset list could not be read — check the keys and paper mode"}


@router.post("/alpaca/test")
async def alpaca_test(payload: dict = Body(default={})) -> dict[str, Any]:
    """Validate a key pair against Alpaca and report what the account can reach.

    §83: the `save` branch writes through ``merge_config`` (whole config ← the alpaca block).
    It used to call ``save_config`` with the ALPACA BLOCK as if it were the whole config —
    and ``save_config`` merges over the DEFAULTS, so pressing "Validate & save" reset every
    other setting and parked the keys at the top level of the file, where the next launch's
    ``alpaca`` block could not see them (the reported "I had to re-enter my keys").
    """
    from orderflow_system.desktop import alpaca as alpaca_mod

    full = config_store.load_config()
    cfg = dict(full.get("alpaca") or {})
    # SEC-09: masked/blank fields test the STORED pair; only a typed value replaces it.
    body = {
        "key_id": config_store.secret_or_stored(full, "alpaca.key_id", payload.get("key_id")),
        "secret": config_store.secret_or_stored(full, "alpaca.secret", payload.get("secret")),
        "paper": payload.get("paper", cfg.get("paper", True)),
    }
    report = await asyncio.to_thread(alpaca_mod.probe, body)
    if report.get("ok") and payload.get("save"):
        cfg.update({"key_id": body["key_id"], "secret": body["secret"],
                    "paper": bool(body["paper"]), "enabled": True})
        # The block, merged over what is on disk — never a whole-config write from a block.
        saved = config_store.merge_config({"alpaca": cfg})
        report["saved"] = bool((saved.get("alpaca") or {}).get("secret"))
        report["key_masked"] = alpaca_mod.mask_key(str(cfg.get("key_id") or ""))
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
                           "active": [], "view": "", "last_active": 0.0, "data": None,
                           "ctx": None, "ctx_at": 0.0}

#: MEM-B-01/B-02: how long the palette reuses one config/capability read while it is open.
_SEARCH_CTX_TTL_S = 5.0


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


def _search_live_ctx(caps: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """The constants the row builder needs, read once per search / pump flush (MEM-B-01/B-02).

    The row path used to re-read and re-merge the whole config for *every* row: measured
    4,055 loads and 7.5 s of event-loop freeze per keystroke on a linked account. The
    capability block only changes when the config does, so it is read here and handed down.
    """
    if caps is not None:
        return {"caps": caps}
    now = time.time()
    held = _SEARCH.get("ctx")
    if held is not None and (now - float(_SEARCH.get("ctx_at") or 0.0)) < _SEARCH_CTX_TTL_S:
        return held
    ctx = {"caps": engine_mod.alpaca_capability_block(config_store.load_config(), None)}
    _SEARCH["ctx"] = ctx
    _SEARCH["ctx_at"] = now
    return ctx


def _search_live_provider(symbol: str, ctx: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Live fields for one palette row — from the engine, never invented.

    ``ctx`` is the per-search constant block (:func:`_search_live_ctx`); when it is missing
    the block is read here — correct, but it costs one config load per row.
    """
    system = engine_mod.engine.system
    if system is None:
        return {}
    key = str(symbol or "").upper()
    if not key:
        return {}
    out: dict[str, Any] = {}
    # The palette lists app symbols, but the rows that arrive from Alpaca wear
    # Alpaca's spelling (BTC/USD): map both ways through the capability block.
    caps = (ctx or {}).get("caps") or engine_mod.alpaca_capability_block(config_store.load_config(), None)
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
        elif source == "all":
            # `all` runs every leg, so answer with the leg this symbol actually lands on —
            # the partition is the one rule for that (engine.partition_instruments)
            part = engine_mod.partition_instruments(
                cfg, [symbol], legs=("bybit", "alpaca", "mt5", "ninjatrader"))
            leg = next((name for name, syms in part.items() if symbol in syms), "")
            if leg:
                local_feeds[symbol] = leg
    # MEM-B-01: one read of the capability block per search, not one per row.
    live_ctx = _search_live_ctx(caps=caps)
    universe = search_service.SymbolUniverse(
        config=cfg,
        assets_provider=(data.assets if data else None),
        clock_provider=(lambda: clock) if clock else None,
        live_provider=lambda symbol: _search_live_provider(symbol, live_ctx),
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
            rows = _search_pump_tick()
            if rows:
                await ws_manager.broadcast_search_rows(rows)
        except asyncio.CancelledError:
            raise
        except Exception:                       # noqa: BLE001 — the palette must never kill the app
            logger.debug("search pump tick failed", exc_info=True)


def _search_pump_tick() -> list[dict[str, Any]]:
    """One pump pass: read the constants once, offer every active symbol, return due rows.

    MEM-B-02: the config/capability block is read once per flush (5 s TTL) — never per
    symbol — and a tick whose batch window has not closed costs nothing at all.
    """
    batcher = _SEARCH.get("batcher")
    if batcher is None or not _SEARCH["active"]:
        return []
    if not batcher.due():
        return []
    ctx = _search_live_ctx()
    for symbol in list(_SEARCH["active"]):
        patch = _search_live_provider(symbol, ctx)
        if patch:
            batcher.offer(symbol, patch)
    return batcher.drain()


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
        stored = [str(r).upper() for r in (cfg.get("search", {}).get("recents") or [])]
        recents = [r for r in (cfg.get("search", {}).get("recents") or []) if r.upper() != focus]
        recents.insert(0, focus)
        # MEM-B-06: only a real change is persisted — re-focusing the same row used to rewrite
        # the whole config (and its version ring) for a list that did not move.
        if [str(r).upper() for r in recents[:12]] != stored[:12]:
            cfg.setdefault("search", {})["recents"] = recents[:12]
            try:
                config_store.save_config(cfg)
            except Exception:                    # noqa: BLE001 — never fail the palette on a save
                logger.debug("recents save failed", exc_info=True)

    snapshot_ctx = _search_live_ctx()
    rows = [_search_row_snapshot(s, snapshot_ctx) for s in symbols]
    return {"ok": True, "active": len(symbols), "rows": [r for r in rows if r],
            "counters": (_SEARCH["batcher"].counters() if _SEARCH.get("batcher") else {})}


def _search_row_snapshot(symbol: str, ctx: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
    patch = _search_live_provider(symbol, ctx)
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
    # SEC-09: an untouched (masked) token field tests the STORED token, never the bullets.
    token = str(config_store.secret_or_stored(cfg, "telegram.bot_token", payload.get("bot_token")) or "").strip()
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
#: Handles of the fire-and-forget jobs, kept by reference: a discarded task can be collected
#: mid-flight and nothing could then answer "is it still running?" (audit A-06).
_backfill_task: Optional[asyncio.Task] = None
_update_check_task: Optional[asyncio.Task] = None


def _backfill_job_public() -> dict[str, Any]:
    # The task handle is internal bookkeeping and must never leak into a JSON response.
    return {key: value for key, value in _backfill_job.items() if key != "task"}


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
    global _backfill_task
    _backfill_task = asyncio.create_task(_run_backfill(symbol, days))
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
    cache (`?refresh=1` forces a fresh read). With the engine stopped the live handle is gone
    but the file is still on disk, so the stopped path reads it READ-ONLY: sizes, page
    accounting, the reclaimable bytes and the per-instrument tick span. Row counts still need
    the engine, and the last prune is read back from the store — a restart can no longer make
    it read "never".
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
        # No engine handle: the file itself still answers — a stopped app is exactly when a user
        # opens the Logs panel, and "nothing to see" is not an answer.
        from orderflow_system.data.database import readonly_snapshot  # MEM-A2-11: off the loop below

        # MEM-A2-11: a covering-index scan over a stopped engine's store measured 0.76 s —
        # in a worker thread, never on the loop.
        snap = await asyncio.to_thread(readonly_snapshot, str(config_store.db_path()))
        snap.setdefault("tables", {})              # counts are the live handle's business
        last_prune = config_store.load_last_prune()

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
    # R6: the panels that manage storage need the whole picture — where the bytes are, where the
    # curve points, what the backup job is set to, and what sets already exist in the target.
    from orderflow_system.desktop import storage as storage_mod

    settings = storage_mod.clamp_storage_settings(config_store.load_config())
    config_dir = config_store.config_dir()
    target = storage_mod.resolved_target(settings, config_dir)
    usage = await asyncio.to_thread(storage_mod.usage_snapshot, config_store.db_path(),
                                    config_dir=config_dir, target=target)
    store = storage_mod.load_usage_store(storage_mod.usage_store_path(config_dir))
    out["usage"] = usage
    out["growth"] = storage_mod.growth_report(store.get("samples", []),
                                              usage["db_bytes"] + usage["wal_bytes"],
                                              retention_days=int(rt[0] or 0))
    out["storage_settings"] = settings
    out["backups"] = await asyncio.to_thread(storage_mod.list_backups, target)
    email_cfg = dict((config_store.load_config().get("notify") or {}).get("email") or {})
    out["smtp_configured"] = bool(email_cfg.get("host") and email_cfg.get("to"))
    out["smtp_to"] = str(email_cfg.get("to") or "")
    out["email_report"] = bool(settings.get("email_report") or settings.get("email_threshold"))
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


@router.post("/storage/settings")
async def set_storage_settings(payload: dict = Body(default={})) -> dict[str, Any]:
    """Save the storage block and the retention window beside it — clamped by the one helper.

    The response carries the clamped values back, because those are what the jobs will use: the
    panel must show the numbers in force, not the ones that were typed. Retention edits apply to
    the next prune pass and the next engine start, live ones included — the jobs re-read the
    config rather than trusting the boot-time copy.
    """
    from orderflow_system.desktop import storage as storage_mod

    body = dict(payload or {})
    patch: dict[str, Any] = {}
    data_block = {k: v for k, v in body.items()
                  if k in ("retention_days", "prune_interval_hours", "session_start_hour")}
    if data_block:
        patch["data"] = data_block
    storage_block = {k: v for k, v in body.items() if k in storage_mod.DEFAULT_SETTINGS}
    if storage_block:
        patch["storage"] = storage_block
    if not patch:
        return {"ok": False, "error": "nothing to save — send retention_days / prune_interval_hours / storage keys"}
    saved = config_store.merge_config(patch)
    _storage_cache["at"] = 0.0
    _storage_cache["data"] = None
    from orderflow_system.desktop.engine import clamp_data_settings

    sh, rd, ph = clamp_data_settings(saved)
    return {"ok": True, "storage": storage_mod.clamp_storage_settings(saved),
            "retention": {"days": rd, "prune_interval_hours": ph, "session_start_hour": sh}}


@router.post("/storage/backup")
async def storage_backup(payload: dict = Body(default={})) -> dict[str, Any]:
    """Run one backup now, to the configured target or the one in the body.

    The body may name a target (a folder, a UNC share, a removable drive…), a format and how many
    sets to keep — the same parameters the scheduled job uses, so "try it once" and "run it
    nightly" are one code path with the same failure messages. An unreachable share is a 400 with
    the operating system's reason, not a hang.
    """
    from orderflow_system.desktop import storage as storage_mod

    body = dict(payload or {})
    cfg = config_store.load_config()
    settings = storage_mod.clamp_storage_settings(cfg)
    target = (str(body.get("target") or "").strip()
              or str(storage_mod.resolved_target(settings, config_store.config_dir())))
    fmt = str(body.get("format") or settings["backup_format"])
    try:
        keep = int(body.get("keep") or settings["backup_keep"])
    except (TypeError, ValueError):
        keep = int(settings["backup_keep"])
    try:
        # SEC-30: the target arrives in the request body — check it before anything is written.
        target = storage_mod.validate_target(target)
    except storage_mod.StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        manifest = await asyncio.to_thread(storage_mod.run_backup, config_store.db_path(),
                                           target, fmt=fmt, keep=keep)
    except storage_mod.StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _storage_cache["at"] = 0.0
    _storage_cache["data"] = None
    return {"ok": True, "backup": manifest}


@router.get("/storage/backups")
async def storage_backups(target: str = Query(default="")) -> dict[str, Any]:
    """The sets already in the target, newest first, with their manifests."""
    from orderflow_system.desktop import storage as storage_mod

    settings = storage_mod.clamp_storage_settings(config_store.load_config())
    folder = str(target or "").strip() or str(storage_mod.resolved_target(settings, config_store.config_dir()))
    try:
        folder = str(storage_mod.validate_target(folder))        # SEC-30: same check on reads
    except storage_mod.StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    sets = await asyncio.to_thread(storage_mod.list_backups, folder)
    return {"ok": True, "target": folder, "sets": sets,
            "total_bytes": sum(int(s.get("bytes") or 0) for s in sets)}


@router.post("/storage/vacuum")
async def storage_vacuum() -> dict[str, Any]:
    """Reclaim free pages. Full VACUUM only with the engine stopped — with a writer live, the
    incremental pass is the honest one (the app keeps auto_vacuum on for exactly that)."""
    from orderflow_system.desktop import engine as engine_mod
    from orderflow_system.desktop import storage as storage_mod

    live = getattr(engine_mod.engine, "_system", None) is not None
    result = await asyncio.to_thread(storage_mod.vacuum_now, config_store.db_path(),
                                     allow_full=not live)
    result["engine_running"] = live
    _storage_cache["at"] = 0.0
    _storage_cache["data"] = None
    return {"ok": bool(result.get("ok")), **result}


@router.post("/storage/report")
async def storage_report_mail() -> dict[str, Any]:
    """Email the storage report (plain text + a CSV attachment) to the configured address."""
    from orderflow_system.desktop import storage as storage_mod

    cfg = config_store.load_config()
    settings = storage_mod.clamp_storage_settings(cfg)
    config_dir = config_store.config_dir()
    target = storage_mod.resolved_target(settings, config_dir)
    usage = await asyncio.to_thread(storage_mod.usage_snapshot, config_store.db_path(),
                                    config_dir=config_dir, target=target)
    store = storage_mod.load_usage_store(storage_mod.usage_store_path(config_dir))
    data_block = dict(cfg.get("data") or {})
    days = int(data_block.get("retention_days", 0) or 0)
    growth = storage_mod.growth_report(store.get("samples", []),
                                       usage["db_bytes"] + usage["wal_bytes"], retention_days=days)
    subject, body, csv_text = storage_mod.build_report(
        usage, growth,
        {"days": days, "prune_interval_hours": data_block.get("prune_interval_hours", 0),
         "session_start_hour": data_block.get("session_start_hour", 0)},
        await asyncio.to_thread(storage_mod.list_backups, target), config_store.load_last_prune())
    result = await storage_mod.email_report(cfg, subject, body, attachments=[
        ("storage-summary.csv", csv_text.encode("utf-8"), "text/csv")])
    return {"ok": bool(result.get("ok")), "subject": subject, "error": result.get("error", ""),
            "preview": body}


@router.post("/storage/clear_cache")
async def storage_clear_cache() -> dict[str, Any]:
    """Clear the WebView2 app cache: the cache folders now, the locked rest at the next start.

    The open window holds its own profile, so most of it cannot be deleted while the app runs;
    the flag this pass may leave behind is honoured by the launcher before WebView2 starts.
    """
    from orderflow_system.desktop import storage as storage_mod

    result = await asyncio.to_thread(storage_mod.clear_app_cache, config_store.config_dir())
    _storage_cache["at"] = 0.0
    _storage_cache["data"] = None
    return result


@router.post("/storage/clear_archive")
async def storage_clear_archive() -> dict[str, Any]:
    """Delete the archive/quarantine folder's contents — the folder itself stays (it is the app's)."""
    from orderflow_system.desktop import storage as storage_mod

    result = await asyncio.to_thread(storage_mod.clear_archive, config_store.config_dir())
    _storage_cache["at"] = 0.0
    _storage_cache["data"] = None
    return result


# ──────────────────────────────────────────────────────────────
# Program updates (R7): check on load, regularly while open, download on request
# ──────────────────────────────────────────────────────────────

_update_state: dict[str, Any] = {"checking": False}


def _updates_state() -> dict[str, Any]:
    """The remembered check result + the settings in force + the running build. Cheap, no wire."""
    from orderflow_system.desktop import updater as updater_mod

    cfg = config_store.load_config()
    settings = updater_mod.clamp_update_settings(cfg)
    cached = updater_mod.load_cache(updater_mod.cache_path(config_store.config_dir()))
    state: dict[str, Any] = dict(cached) if isinstance(cached, dict) else {}
    state.setdefault("current", updater_mod.local_version())
    state.setdefault("release_page", updater_mod.RELEASE_PAGE)
    latest_version = str((state.get("latest") or {}).get("version") or "")
    skipped = str(settings.get("skipped_version") or "")
    state["skipped"] = bool(skipped) and latest_version == skipped
    if state["skipped"]:
        state["update_available"] = False
    return {"ok": True, "settings": settings, "checking": bool(_update_state["checking"]),
            "download_dir": str(updater_mod.resolved_download_dir(settings, config_store.config_dir())),
            "state": state}


async def _update_auto_download(result: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """Fetch the release's artefact — the mode='download' half of a check. Never raises."""
    from orderflow_system.desktop import updater as updater_mod

    asset = (result.get("latest") or {}).get("asset") or {}
    if not asset.get("url"):
        return {"ok": False, "error": "the release carries no downloadable artefact"}
    dest = updater_mod.resolved_download_dir(settings, config_store.config_dir())
    done = await asyncio.to_thread(updater_mod.download_asset, str(asset["url"]), dest,
                                   name=str(asset.get("name") or ""),
                                   expected_sha256=str(asset.get("sha256") or ""))
    if done.get("ok"):
        logger.info("[update] artefact ready: %s (%d bytes, verified=%s)",
                    done.get("path"), int(done.get("bytes") or 0), done.get("verified"))
    else:
        logger.warning("[update] download failed: %s", done.get("error"))
    return done


async def _run_update_check(settings: dict[str, Any], claimed: bool = False) -> dict[str, Any]:
    """One check: off the loop, remembered to disk, stamped into the config. Never raises.

    ``claimed`` means the caller already set ``_update_state["checking"]`` — the status route
    claims it before creating this task so two requests cannot both start a check (audit A-06).
    """
    from orderflow_system.desktop import updater as updater_mod

    if _update_state["checking"] and not claimed:
        return _updates_state()
    _update_state["checking"] = True
    try:
        result = await asyncio.to_thread(updater_mod.check_for_update, channel=str(settings.get("channel") or "stable"))
    finally:
        _update_state["checking"] = False
    config_dir = config_store.config_dir()
    updater_mod.save_cache(updater_mod.cache_path(config_dir), result)
    try:                                    # the interval must survive a restart to mean anything
        config_store.merge_config({"updates": {"last_check_ms": int(result.get("checked_at_ms") or 0)}})
    except Exception:                       # noqa: BLE001 - a stamp is not worth a failure
        logger.debug("could not record the update check time", exc_info=True)
    latest = (result.get("latest") or {}).get("version")
    mine = (result.get("current") or {}).get("display")
    if result.get("ok") and result.get("update_available"):
        logger.info("[update] %s is available (running %s)", latest, mine)
        fresh = updater_mod.clamp_update_settings(config_store.load_config())
        if fresh["mode"] == "download":
            await _update_auto_download(result, fresh)
    elif not result.get("ok"):
        logger.info("[update] check failed: %s", result.get("error"))
    else:
        logger.info("[update] up to date (%s)", mine)
    return _updates_state()


@router.get("/update/status")
async def update_status(refresh: int = Query(default=0)) -> dict[str, Any]:
    """The remembered state — and a check when the interval has passed (or `?refresh=1`).

    The panel calls this on load and then on its own slow cadence, so "check on load" and "check
    regularly" are the same debounced call: the wire is asked once per interval, not once per page.
    """
    from orderflow_system.desktop import updater as updater_mod

    settings = updater_mod.clamp_update_settings(config_store.load_config())
    import time as _time

    global _update_check_task
    if (bool(refresh) or updater_mod.check_due(settings, now_ms=int(_time.time() * 1000))) \
            and not _update_state["checking"]:
        # Claim the flag HERE, not inside the coroutine: the old order let two requests arriving
        # before the first task ran each start a check (audit A-06).
        _update_state["checking"] = True
        _update_check_task = asyncio.create_task(_run_update_check(settings, claimed=True))
    return _updates_state()


@router.post("/update/check")
async def update_check_now() -> dict[str, Any]:
    """Ask now, whoever asked (the menu's Check now). Waits for the answer; a check is seconds."""
    from orderflow_system.desktop import updater as updater_mod

    settings = updater_mod.clamp_update_settings(config_store.load_config())
    return await _run_update_check(settings)


@router.post("/update/skip")
async def update_skip(payload: dict = Body(default={})) -> dict[str, Any]:
    """Remember "not this one" — or clear it by sending an empty version."""
    version = str((payload or {}).get("version") or "").strip()[:40]
    config_store.merge_config({"updates": {"skipped_version": version}})
    return _updates_state()


@router.post("/update/download")
async def update_download(payload: dict = Body(default={})) -> dict[str, Any]:
    """Fetch the release artefact (the picked one, or the name/url the caller asked for).

    The file lands in the update folder — `<config>/updates` unless the user pointed elsewhere —
    verified against the release's own SHA-256 when GitHub supplies one.
    """
    from orderflow_system.desktop import updater as updater_mod

    body = dict(payload or {})
    settings = updater_mod.clamp_update_settings(config_store.load_config())
    state = _updates_state()["state"]
    latest = dict(state.get("latest") or {})
    assets = [a for a in (latest.get("assets") or []) if isinstance(a, dict)]
    wanted = str(body.get("name") or "").strip()
    url = str(body.get("url") or "").strip()
    sha = ""
    if wanted:
        match = next((a for a in assets if str(a.get("name")) == wanted), None)
        if match is None:
            return {"ok": False, "error": f"the release carries no asset named {wanted!r}"}
        url, sha = str(match.get("url") or ""), str(match.get("sha256") or "")
    elif not url:
        asset = latest.get("asset") or {}
        url, sha = str(asset.get("url") or ""), str(asset.get("sha256") or "")
    if not url:
        return {"ok": False, "error": "nothing to download — run a check first"}
    dest = updater_mod.resolved_download_dir(settings, config_store.config_dir())
    done = await asyncio.to_thread(updater_mod.download_asset, url, dest,
                                   name=str(body.get("filename") or ""), expected_sha256=sha)
    return {"ok": bool(done.get("ok")), "download": done, "download_dir": str(dest)}


@router.post("/update/settings")
async def update_settings(payload: dict = Body(default={})) -> dict[str, Any]:
    """Save the updates block (clamped) — mode, interval, channel, download folder."""
    from orderflow_system.desktop import updater as updater_mod

    body = dict(payload or {})
    block = {k: v for k, v in body.items() if k in updater_mod.DEFAULT_SETTINGS}
    if not block:
        return {"ok": False, "error": "nothing to save — send mode / interval_hours / channel / download_dir"}
    saved = config_store.merge_config({"updates": block})
    return {"ok": True, "settings": updater_mod.clamp_update_settings(saved)}


@router.post("/update/open")
async def update_open(payload: dict = Body(default={})) -> dict[str, Any]:
    """Open the update folder in the file browser, or the release page in the default browser."""
    import os as _os
    import subprocess
    import sys as _sys
    import webbrowser

    from orderflow_system.desktop import updater as updater_mod

    what = str((payload or {}).get("what") or "downloads").strip().lower()
    if what == "page":
        try:
            webbrowser.open(updater_mod.RELEASE_PAGE)
        except Exception as exc:                     # noqa: BLE001 - a headless run has no browser
            return {"ok": False, "error": str(exc), "url": updater_mod.RELEASE_PAGE}
        return {"ok": True, "opened": updater_mod.RELEASE_PAGE}
    settings = updater_mod.clamp_update_settings(config_store.load_config())
    folder = updater_mod.resolved_download_dir(settings, config_store.config_dir())
    try:
        folder.mkdir(parents=True, exist_ok=True)
        if _sys.platform.startswith("win"):
            _os.startfile(str(folder))               # type: ignore[attr-defined]
        elif _sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except Exception as exc:                         # noqa: BLE001
        return {"ok": False, "error": str(exc), "path": str(folder)}
    return {"ok": True, "path": str(folder)}


# ──────────────────────────────────────────────────────────────
# Journal (R10) — the trade journal and its statement
# ──────────────────────────────────────────────────────────────

def _journal_rows(limit: int = 1000) -> list[dict[str, Any]]:
    """Read the journal table read-only: the panel and the statement both work with the app down."""
    import sqlite3

    path = Path(config_store.db_path())
    if not path.exists():
        return []
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        # A file the engine has not opened since the profiles column shipped still has to render:
        # fall back to an empty string rather than letting the missing column blank the journal.
        cols = {row[1] for row in conn.execute("PRAGMA table_info(trade_journal)").fetchall()}
        profile_col = "profile_id" if "profile_id" in cols else "'' AS profile_id"
        # §148: the excursion columns arrived with the MAE/MFE writers — a file written before them
        # (or before the data layer's migration ran) reads as no excursion rather than failing.
        mae_col = "mae_ticks" if "mae_ticks" in cols else "NULL AS mae_ticks"
        mfe_col = "mfe_ticks" if "mfe_ticks" in cols else "NULL AS mfe_ticks"
        cursor = conn.execute(
            "SELECT id, instrument, direction, entry_time_ms, exit_time_ms, entry_price, "
            "exit_price, stop_loss, take_profit, pnl_ticks, rr_ratio, signals_json, notes, "
            f"{mae_col}, {mfe_col}, "
            f"{profile_col} "
            "FROM trade_journal ORDER BY COALESCE(exit_time_ms, entry_time_ms, 0) DESC LIMIT ?",
            (int(limit),))
        return [dict(row) for row in cursor]
    except sqlite3.OperationalError:            # a database from before the journal existed
        return []
    finally:
        conn.close()


@router.get("/journal")
async def journal_view(limit: int = Query(default=500, ge=1, le=5000)) -> dict[str, Any]:
    """The journal: rows, their statistics and the daily curve. Read-only."""
    from orderflow_system.desktop import journal as journal_mod

    rows = await asyncio.to_thread(_journal_rows, limit)
    trades = journal_mod.normalise_trades(rows)
    return {"ok": True, "rows": rows, "count": len(rows), "stats": journal_mod.stats(trades),
            "daily": journal_mod.daily_series(trades)}


@router.post("/journal/note")
async def journal_note(payload: dict = Body(default={})) -> dict[str, Any]:
    """Write one trade's note — the only field the user edits in place."""
    import sqlite3

    body = dict(payload or {})
    try:
        trade_id = int(body.get("id"))
    except (TypeError, ValueError):
        return {"ok": False, "error": "which trade? send its id"}
    note = str(body.get("notes") or "")[:2000]
    conn = sqlite3.connect(str(config_store.db_path()), timeout=15)
    try:
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("UPDATE trade_journal SET notes = ? WHERE id = ?", (note, trade_id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "id": trade_id, "notes": note}


@router.post("/journal/statement")
async def journal_statement() -> dict[str, Any]:
    """Write the broker-style HTML statement into the exports folder (R10) and return its path."""
    import time as _time

    from orderflow_system.desktop import journal as journal_mod

    rows = await asyncio.to_thread(_journal_rows, 5000)
    trades = journal_mod.normalise_trades(rows)
    try:
        from orderflow_system import __version__
        from orderflow_system.desktop.help import APP_CHANNEL

        version = f"{__version__}-{APP_CHANNEL}"
    except Exception:                            # noqa: BLE001 - a header without a version is fine
        version = ""
    html = journal_mod.html_statement(
        trades, journal_mod.stats(trades),
        meta={"app": "ModFlow OrderFlow Analysis Suite", "version": version,
              "account": "local journal — simulated and manual trades"})
    folder = _exports_dir()
    folder.mkdir(parents=True, exist_ok=True)
    name = "journal-statement-" + _time.strftime("%Y%m%d-%H%M%S", _time.gmtime()) + ".html"
    target = folder / name
    target.write_text(html, encoding="utf-8")
    logger.info("[journal] statement written: %s (%d trades)", target, len(trades))
    return {"ok": True, "path": str(target), "bytes": len(html), "trades": len(trades)}


# ──────────────────────────────────────────────────────────────
# Economic calendar (R11) — keyless weekly feed, cached
# ──────────────────────────────────────────────────────────────

def _calendar_cache_path() -> Path:
    return config_store.config_dir() / "calendar-cache.json"


def _calendar_lane(cfg: dict[str, Any], override: str = "") -> str:
    """Which feed the calendar VIEW reads: "builtin" (the keyless weekly JSON) or "finnhub".

    The stored `calendar.source` is the default and a caller may override it for one read (the
    settings card's own check). Anything unknown falls back to the keyless lane, so a hand-edited
    file can never make the view read nothing at all.
    """
    stored = str((cfg.get("calendar") or {}).get("source") or "builtin").lower()
    lane = str(override or "").strip().lower() or stored
    return lane if lane in ("builtin", "finnhub") else "builtin"


def _finnhub_key() -> str:
    """The Finnhub key the app holds: the settings copy first (what the engine applied), then the
    stored config block. Read-only, never logged, never echoed back."""
    from orderflow_system.config import settings

    key = str(getattr(settings.FINNHUB, "api_key", "") or "").strip()
    if key:
        return key
    block = (config_store.load_config() or {}).get("finnhub") or {}
    return str(block.get("api_key") or "").strip()


def _finnhub_calendar(category: str, days: int):
    """The Finnhub economic calendar — blocking, so every caller runs it on a worker thread."""
    from orderflow_system.data import finnhub_feed as fh

    return fh.FinnhubFeed(api_key=_finnhub_key()).calendar(category=category, days=days)


@router.get("/calendar")
async def calendar_view(hours: int = Query(default=48, ge=1, le=720),
                        currencies: str = Query(default=""),
                        impact: str = Query(default="high"),
                        source: str = Query(default="")) -> dict[str, Any]:
    """The releases coming up, filtered — with the honest state of the feed it came from.

    Two lanes, one shape. ``builtin`` (the default) is the keyless weekly JSON, cached for four
    hours by the module; ``finnhub`` is the Finnhub economic calendar read with the key from
    Settings ▸ Feed keys (`calendar.source` in the config picks the lane). Either lane answers
    ``ok: false`` with the reason when its feed cannot be read — the panel says so instead of
    inventing dates. The alert line (main.py's calendar tick) keeps reading the built-in lane:
    a keyed lane is a view, not a background dependency.
    """
    import time as _time

    from orderflow_system.desktop import calendar as calendar_mod

    cfg = config_store.load_config()
    lane = _calendar_lane(cfg, source)
    now_ms = int(_time.time() * 1000)
    error_text = ""

    if lane == "finnhub":
        block = cfg.get("finnhub") or {}
        if not _finnhub_key():
            return {"ok": False, "stale": False, "lane": "finnhub", "fetched_at_ms": None,
                    "error": "no Finnhub key — add one in Settings ▸ Feed keys to read this lane",
                    "events": [], "upcoming": 0, "total": 0, "currencies": [],
                    "window_hours": hours, "min_impact": impact,
                    "source": "Finnhub economic calendar (needs a key)"}
        failure = ""
        payload = None
        try:
            payload = await asyncio.to_thread(_finnhub_calendar,
                                              str(block.get("calendar_category") or "all"),
                                              int(block.get("calendar_days") or 7))
        except Exception as exc:                       # pragma: no cover - the feed never raises
            failure = f"{type(exc).__name__}: {exc}"
        if payload is None or getattr(payload, "error", None):
            reason = failure or str(getattr(payload, "error", "") or "the calendar could not be read")
            return {"ok": False, "stale": False, "lane": "finnhub", "fetched_at_ms": None,
                    "error": f"the Finnhub calendar answered: {reason}",
                    "events": [], "upcoming": 0, "total": 0, "currencies": [],
                    "window_hours": hours, "min_impact": impact,
                    "source": "Finnhub economic calendar (your key)"}
        from orderflow_system.data import finnhub_feed as _fh
        events = _fh.to_calendar_rows(getattr(payload, "events", None))
        fetched_ms = int(getattr(payload, "fetched_ms", 0) or now_ms)
        stale, ok = False, True
        source_label = "Finnhub economic calendar — your key (events labelled by country)"
    else:
        payload = await asyncio.to_thread(calendar_mod.fetch_events_cached, _calendar_cache_path(),
                                          ttl_s=4 * 3600)
        events = [e for e in (payload.get("events") or []) if isinstance(e, dict)]
        fetched_ms, stale = payload.get("fetched_at_ms"), bool(payload.get("stale"))
        ok = bool(payload.get("ok"))
        error_text = str(payload.get("error") or "")
        source_label = "Forex Factory weekly calendar JSON (nfs.faireconomy.media) — keyless"

    up = calendar_mod.upcoming(events, now_ms=now_ms, within_hours=float(hours),
                               currencies=currencies or None, min_impact=impact)
    # §130: the currencies this window holds at this impact — the filter chips' own domain.
    # Computed WITHOUT the currency filter: a chip row that collapsed to the current selection
    # could never widen it again. Each code carries the count it would show, so a chip reads
    # before it is clicked.
    available: dict[str, int] = {}
    for e in calendar_mod.upcoming(events, now_ms=now_ms, within_hours=float(hours),
                                   currencies=None, min_impact=impact):
        code = str(e.get("currency") or "").upper()
        if code:
            available[code] = available.get(code, 0) + 1
    return {"ok": ok, "stale": stale, "lane": lane, "error": error_text,
            "fetched_at_ms": fetched_ms,
            "events": up, "upcoming": len(up), "total": len(events),
            "currencies": [{"code": c, "count": n} for c, n in sorted(available.items())],
            "window_hours": hours, "min_impact": impact,
            "source": source_label}


# ──────────────────────────────────────────────────────────────
# Feed keys (the optional REST feeds: OPRA option chains + Finnhub)
# ──────────────────────────────────────────────────────────────

#: The optional REST feeds, in the card's order: block name, display name, what a key buys, and the
#: leaves this route accepts for it. The whitelist lives here because the store keeps whatever a
#: block holds — the route is the only place a leaf set is decided, so a hand-crafted POST cannot
#: add one. `enabled` is deliberately NOT offered: nothing reads it (a key's presence is what makes
#: a lane work), and a switch no layer honours is the kind of lie this suite removes.
_FEED_KEY_BLOCKS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("tradier", "Tradier",
     "real-time OPRA option chains for US equities — a free brokerage account is enough",
     ("key_id", "secret", "chain_width", "sandbox")),
    ("marketdata", "Market Data",
     "OPRA chains with server-side greeks — a marketdata.app account",
     ("api_key",)),
    ("finnhub", "Finnhub",
     "the economic calendar and market headlines — Finnhub's free tier",
     ("api_key", "calendar_category", "calendar_days", "news_category")),
)


def _feed_key_row(name: str, label: str, buys: str, leaves: tuple[str, ...],
                  cfg: dict[str, Any]) -> dict[str, Any]:
    """One card row: the stored values, with every credential reduced to a hint.

    A stored key never travels back to the page — the row carries ``key_hint`` (first four and
    last two characters, ``alpaca.mask_key``'s shape) and ``has_secret``, so the card can say
    "saved" without holding the value. A blank field means "leave what is stored".
    """
    from orderflow_system.desktop import alpaca as alpaca_mod

    block = cfg.get(name) or {}
    row: dict[str, Any] = {"id": name, "label": label, "buys": buys, "leaves": list(leaves),
                           "key_hint": "", "has_secret": False, "values": {}}
    for leaf in leaves:
        value = block.get(leaf)
        if leaf in ("key_id", "api_key"):
            row["key_hint"] = alpaca_mod.mask_key(str(value or ""))
            row["values"][leaf] = ""
        elif leaf == "secret":
            row["has_secret"] = bool(str(value or "").strip())
        else:
            row["values"][leaf] = value
    row["ready"] = bool(row["key_hint"] or row["has_secret"])
    return row


def _feed_keys_state(cfg: dict[str, Any]) -> dict[str, Any]:
    """The card's whole payload: one row per feed, plus the two lanes' own choices."""
    cal = cfg.get("calendar") or {}
    ctx = cfg.get("context") or {}
    return {"feeds": [_feed_key_row(name, label, buys, leaves, cfg)
                      for name, label, buys, leaves in _FEED_KEY_BLOCKS],
            "lanes": {"calendar": str(cal.get("source") or "builtin"),
                      "news": str(ctx.get("news_source") or "feeds")}}


@router.get("/feedkeys")
async def feed_keys() -> dict[str, Any]:
    """The optional REST feeds' stored state, credentials masked (the card's only read)."""
    return {"ok": True, **_feed_keys_state(config_store.load_config())}


@router.post("/feedkeys")
async def feed_keys_save(payload: dict = Body(default={})) -> dict[str, Any]:
    """Save the optional REST feeds' keys and lanes, then make them live.

    The body carries per-feed blocks of the whitelisted leaves and an optional ``lanes`` block for
    the calendar / news source pickers. Credential semantics are the store's own, and the card is
    built around them: a leaf the body does NOT mention keeps its stored value (that is how a blank
    field behaves — it is left out of the request), an explicit empty string clears it, and the
    bullet mask a masked round-trip carries is replaced by the stored value. `apply_settings` runs
    after the write, so the chain panels, the calendar lane and the news lane read a key that was
    typed a second ago — no engine restart, no stale settings copy. The answer is the fresh state,
    masked, exactly like the GET.
    """
    body = dict(payload or {})
    patch: dict[str, Any] = {}
    for name, _label, _buys, leaves in _FEED_KEY_BLOCKS:
        block = body.get(name)
        if isinstance(block, dict):
            patch[name] = {leaf: block[leaf] for leaf in leaves if leaf in block}
    lanes = body.get("lanes") if isinstance(body.get("lanes"), dict) else {}
    if "calendar" in lanes:
        lane = str(lanes.get("calendar") or "builtin").strip().lower()
        patch["calendar"] = {"source": lane if lane in ("builtin", "finnhub") else "builtin"}
    if "news" in lanes:
        lane = str(lanes.get("news") or "feeds").strip().lower()
        patch["context"] = {"news_source": lane if lane in ("feeds", "finnhub") else "feeds"}
    if not patch:
        return {"ok": False, "error": "no feed block in the body"}
    saved = config_store.merge_config(patch)
    applied = True
    try:
        engine_mod.apply_settings(saved)
    except Exception as exc:                            # pragma: no cover - the cast never raises
        logger.warning("apply_settings after feed keys failed: %s", exc)
        applied = False
    return {"ok": True, "applied": applied, **_feed_keys_state(saved)}


@router.post("/data/import")
async def data_import(payload: dict = Body(default={})) -> dict[str, Any]:
    """Load a CSV of prints or bars into the suite's own database (R8).

    Takes the app's own export shape, an MT5/Sierra/Databento-style CSV, or no header at all;
    timestamps may be epoch seconds, epoch milliseconds or ISO 8601, and the delimiter is sniffed.
    Unreadable rows are counted with their reason — nothing is guessed. Prints are matched against
    what is already stored in the imported window (so re-running a file does not double the tape);
    bars replace per (instrument, timestamp, timeframe), so a correction re-imports as a correction.
    """
    from orderflow_system.desktop import dataport

    body = dict(payload or {})
    text = str(body.get("text") or "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="no CSV text in the body")
    if len(text) > 40_000_000:
        raise HTTPException(status_code=413, detail=(
            "that file is over 40 MB — split it by day; a day of prints is what the views read at once"))
    kind = "candles" if str(body.get("kind") or "ticks").lower().startswith("candle") else "ticks"
    symbol = str(body.get("symbol") or "").strip().upper()
    has_header = body.get("has_header")
    try:
        # MEM-A2-01: the parse of a 40 MB CSV costs ~15 s of CPU and +600 MiB peak — off the
        # loop (a worker thread), so the app keeps serving while the file is read.
        parsed = await asyncio.to_thread(
            dataport.parse_candles if kind == "candles" else dataport.parse_ticks,
            text, symbol=symbol, has_header=has_header if isinstance(has_header, bool) else None)
    except Exception as exc:                           # noqa: BLE001
        # SEC-33: a CSV the sniffer cannot read (the audit's case: a 25 MB single field raises
        # _csv.Error) used to surface as an unhandled 500. Unreadable input is a 400.
        raise HTTPException(status_code=400, detail=(
            f"could not read that CSV — {type(exc).__name__}: {str(exc)[:160]}")) from exc
    if not parsed["rows"]:
        return {"ok": False, "kind": kind, "error": "no readable rows",
                "errors": parsed["errors"][:10], "delimiter": parsed["delimiter"],
                "headers": parsed["headers"]}
    result = await asyncio.to_thread(dataport.import_rows, str(config_store.db_path()),
                                     kind, parsed["rows"])
    # MEM-A2-01: min/max over a generator, not a `stamps` list the size of the file — the
    # payload used to hold three full copies of itself at once (text, rows, stamps).
    first_ms = min((row[1] for row in parsed["rows"]), default=0)
    last_ms = max((row[1] for row in parsed["rows"]), default=0)
    logger.info("[data] imported %d %s row(s) from %s (skipped %d, bad rows %d)",
                result["inserted"], kind, str(body.get("name") or "a pasted CSV")[:60],
                result["skipped_existing"], parsed["skipped"])
    _storage_cache["at"] = 0.0
    _storage_cache["data"] = None
    return {"ok": True, "kind": kind, "inserted": result["inserted"],
            "skipped_existing": result["skipped_existing"],
            "checked_existing": result["checked_existing"],
            "bad_rows": parsed.get("bad_rows", parsed["skipped"]),
            "deduped": parsed.get("deduped", 0), "errors": parsed["errors"][:10],
            "delimiter": parsed["delimiter"], "headers": parsed["headers"],
            "instrument": symbol or (parsed["rows"][0][0] if parsed["rows"] else ""),
            "first_ms": first_ms, "last_ms": last_ms}


@router.post("/data/export")
async def data_export(payload: dict = Body(default={})) -> dict[str, Any]:
    """Write one table (or one instrument's window) to a CSV in the exports folder (R8).

    RFC 4180, CRLF, ISO 8601 UTC stamps — the same shape the backup writer uses, so an export can be
    re-imported through /data/import (pinned by test_dataport.py). Big tables travel gzipped.
    """
    import sqlite3

    from orderflow_system.desktop import dataport

    body = dict(payload or {})
    kind = "candles" if str(body.get("kind") or "ticks").lower().startswith("candle") else "ticks"
    symbol = str(body.get("symbol") or "").strip().upper()

    def _ms(value: Any) -> Any:
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    try:
        limit = max(1, min(5_000_000, int(body.get("limit") or 2_000_000)))
    except (TypeError, ValueError):
        limit = 2_000_000
    try:
        done = await asyncio.to_thread(dataport.export_rows, str(config_store.db_path()), kind,
                                       str(_exports_dir()), symbol=symbol,
                                       from_ms=_ms(body.get("from_ms")), to_ms=_ms(body.get("to_ms")),
                                       limit=limit)
    except (sqlite3.OperationalError, OSError) as exc:
        # RA-02: a fresh profile has no database yet — answer a sentence, not a traceback.
        raise HTTPException(status_code=400, detail=(
            "no tick history to export yet — start the engine or import a CSV first "
            f"({type(exc).__name__})")) from exc
    logger.info("[data] exported %d %s row(s) to %s", done["rows"], kind, done["path"])
    return {"ok": True, "kind": kind, "instrument": symbol, **done}


@router.post("/storage/cleanup")
async def storage_cleanup(payload: dict = Body(default={})) -> dict[str, Any]:
    """Sweep the derived files: the venue backfill cache, and exports older than the window.

    Derived (re-downloadable) or re-creatable only — never the database, the config or a backup.
    """
    import time as _time

    from orderflow_system.data import backfill as backfill_mod

    body = dict(payload or {})
    try:
        keep_days = max(1, min(365, int(body.get("keep_days") or 30)))
    except (TypeError, ValueError):
        keep_days = 30
    cache_dir = Path(config_store.backfill_cache_dir())
    cache_removed = await asyncio.to_thread(backfill_mod.prune_cache, cache_dir, keep_days=keep_days)
    exports = _exports_dir()
    exports_removed: list[str] = []
    cutoff = _time.time() - keep_days * 86400
    if exports.exists():
        for item in exports.iterdir():
            try:
                if item.is_file() and item.stat().st_mtime < cutoff:
                    item.unlink()
                    exports_removed.append(item.name)
            except OSError:
                continue
    _storage_cache["at"] = 0.0
    _storage_cache["data"] = None
    logger.info("[storage] cleanup: %d cache file(s), %d old export(s) removed (keep %d d)",
                cache_removed, len(exports_removed), keep_days)
    return {"ok": True, "cache_files_removed": cache_removed, "exports_removed": exports_removed,
            "keep_days": keep_days, "cache_dir": str(cache_dir), "exports_dir": str(exports)}


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


def _backups_dir() -> Path:
    """Where the backup job writes: the configured target, or the app's own backups folder."""
    from orderflow_system.desktop import storage as storage_mod

    settings = storage_mod.clamp_storage_settings(config_store.load_config())
    return storage_mod.resolved_target(settings, config_store.config_dir())


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

def _layouts_state(block: dict[str, Any], autocull: bool) -> dict[str, Any]:
    """The state the store holds. `autocull` has NO default on purpose: it is read from the config
    the caller just saved, and a default once made every write answer with a stale `True` (found by
    the §129b rebuild probe — turning the switch OFF answered `autocull: True` while the store held
    `False`). Callers must pass `config_store.layout_versions_autocull(<the config in hand>)`."""
    items = block.get("items") if isinstance(block.get("items"), dict) else {}
    versions_in = block.get("versions") if isinstance(block.get("versions"), dict) else {}
    versions: dict[str, list[dict[str, Any]]] = {}
    for ident, ring in versions_in.items():
        if isinstance(ring, list) and ring:
            rows: list[dict[str, Any]] = []
            for row in ring[: config_store.LAYOUT_VERSIONS_MAX]:
                if not isinstance(row, dict):
                    continue
                # The version's own shape, so the menu can say WHAT would come back ("6 widgets,
                # 1 tab") and not only when it was saved (§129).
                entry = row.get("entry") if isinstance(row.get("entry"), dict) else {}
                tabs = entry.get("tabs") if isinstance(entry.get("tabs"), list) else []
                widgets = 0
                for tab in tabs:
                    if isinstance(tab, dict) and isinstance(tab.get("widgets"), list):
                        widgets += len(tab["widgets"])
                rows.append({"at": int(row.get("at") or 0), "name": str(row.get("name") or ""),
                             "tabs": len(tabs), "widgets": widgets})
            if rows:
                versions[str(ident)] = rows
    return {"mode": block.get("mode") or "classic", "active": block.get("active") or "",
            "items": items, "count": len(items), "versions": versions,
            "autocull": bool(autocull), "keep": config_store.LAYOUT_VERSIONS_KEEP,
            "max": config_store.LAYOUT_VERSIONS_MAX}


def _layout_versions_keep(cfg: dict[str, Any]) -> int:
    """How deep a ring may grow right now: the auto-cull depth, or the hard ceiling when it is off."""
    if config_store.layout_versions_autocull(cfg):
        return config_store.LAYOUT_VERSIONS_KEEP
    return config_store.LAYOUT_VERSIONS_MAX


def _cull_layout_versions(block: dict[str, Any], keep: int) -> int:
    """Drop every ring's rows past `keep`; returns how many rows went. The store's clamps already
    bound each ring, so this is only ever the user's own depth arriving."""
    versions = block.get("versions")
    if not isinstance(versions, dict):
        return 0
    dropped = 0
    for ident, ring in list(versions.items()):
        if isinstance(ring, list) and len(ring) > keep:
            dropped += len(ring) - keep
            del ring[keep:]
        if not ring:
            versions.pop(ident, None)
    return dropped


def _push_layout_version(block: dict[str, Any], ident: str, entry: dict[str, Any], keep: int) -> None:
    """Keep the layout as it was before this write — newest first, culled to `keep` (T2's undo)."""
    import time as _time

    versions = block.get("versions")
    if not isinstance(versions, dict):
        versions = block["versions"] = {}
    ring = versions.get(ident)
    if not isinstance(ring, list):
        ring = versions[ident] = []
    ring.insert(0, {"at": int(_time.time() * 1000), "name": str(entry.get("name") or ident)[:40],
                    "entry": json.loads(json.dumps(entry))})
    del ring[max(1, int(keep)):]


@router.get("/layouts")
async def layouts_get() -> dict[str, Any]:
    """Every saved terminal layout, the boot mode and the active layout (straight from the store)."""
    cfg = config_store.load_config()
    block = cfg.get("layouts") if isinstance(cfg.get("layouts"), dict) else {}
    state = _layouts_state(block, config_store.layout_versions_autocull(cfg))
    if os.environ.get("OFAP_SAFE_START") == "1":
        # T2: a safe start boots Classic no matter what the store says; the store is not written.
        state["mode"] = "classic"
        state["safe"] = True
    return {"ok": True, **state}


@router.post("/layouts")
async def layouts_post(payload: dict = Body(default={})) -> dict[str, Any]:
    """One write per call: mode · save · import · duplicate · rename · delete · activate · export ·
    restore_version (a layout's previous version comes back from the ring T2 keeps).

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
    culled = 0

    if payload.get("export"):
        ident = str(payload["export"]).strip().lower()
        entry = items.get(ident)
        flag = config_store.layout_versions_autocull(cfg)      # nothing has been written yet: the state in hand
        if not isinstance(entry, dict):
            return {"ok": False, "action": "export", "error": f"no layout with id {ident!r}",
                    **_layouts_state(block, flag)}
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(entry.get("name") or ident))[:60] or ident
        # the UI hands this straight to /export/save — a bundle is a file the user can keep
        return {"ok": True, "action": "export", "filename": f"layout-{safe}.json",
                "text": json.dumps({"layout": entry}, indent=2), **_layouts_state(block, flag)}

    def _taken() -> set[str]:
        return {str(x.get("name")) for x in items.values() if isinstance(x, dict)}

    def _free_name(base: str) -> str:
        name, n = base, 2
        while name in _taken() and n < 50:
            name, n = f"{base} {n}", n + 1
        return name

    # §129: how deep a version ring may grow right now — read once, so every push below obeys the
    # same rule (auto-cull on → the 5 newest; off → up to the hard ceiling of 10).
    keep_versions = _layout_versions_keep(cfg)

    if isinstance(payload.get("autocull"), bool):
        # The switch itself, and the cull when it is turned ON: the depth the user chose must apply
        # to what is already stored, not only to the next save.
        ui_block = cfg.get("ui") if isinstance(cfg.get("ui"), dict) else {}
        cfg["ui"] = ui_block
        ui_block["layout_versions_autocull"] = payload["autocull"]
        actions.append("autocull")
        keep_versions = _layout_versions_keep(cfg)
        culled = _cull_layout_versions(block, keep_versions)

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
        previous = items.get(wanted_save)
        if isinstance(previous, dict):
            _push_layout_version(block, wanted_save, previous, keep_versions)
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
            _push_layout_version(block, ident, items[ident], keep_versions)   # a delete is recoverable
            items.pop(ident, None)
            if block.get("active") == ident:
                block["active"] = ""

    if isinstance(payload.get("restore_version"), dict):
        rv = payload["restore_version"]
        ident = str(rv.get("id") or "").strip().lower()
        try:
            at = int(rv.get("at") or 0)
        except (TypeError, ValueError):
            at = 0
        ring = (block.get("versions") or {}).get(ident)
        hit = next((row for row in ring if isinstance(row, dict)
                    and int(row.get("at") or 0) == at), None) if isinstance(ring, list) else None
        if isinstance(hit, dict) and isinstance(hit.get("entry"), dict):
            actions.append("restore_version")
            # A restore is a write like any other: the arrangement it is about to replace is kept
            # first, so stepping back is itself steppable-forward (§129). Without this the state
            # you were just looking at was the one state with no way back.
            current = items.get(ident)
            if isinstance(current, dict):
                _push_layout_version(block, ident, current, keep_versions)
            items[ident] = json.loads(json.dumps(hit["entry"]))
        else:
            refused = refused or f"no version of {ident!r} at {at}"

    if isinstance(payload.get("activate"), str) and payload["activate"]:
        ident = payload["activate"].strip().lower()
        if ident in items:
            actions.append("activate")
            block["active"] = ident
        else:
            refused = refused or f"no layout with id {ident!r}"

    saved = config_store.save_config(cfg)
    block_out = saved.get("layouts") if isinstance(saved.get("layouts"), dict) else {}
    state = _layouts_state(block_out, config_store.layout_versions_autocull(saved))
    if wanted_save and wanted_save not in state["items"]:
        return {"ok": False, "action": "save", **state, "actions": actions,
                "error": "the store refused this layout — its id must be a lowercase slug "
                         "(letters, digits, _ or -, starting with a letter or digit)"}
    return {"ok": True, "action": actions[-1] if actions else "read", "actions": actions,
            "error": refused, "culled": culled, **state,
            "note": "layouts live in your config file; the browser keeps no copy"}


# ──────────────────────────────────────────────────────────────
# Profiles — switchable playbooks (feed, instruments, analysis, layout, theme in one switch)
# ──────────────────────────────────────────────────────────────
#
# A profile carries only the analysis blocks in config_store.PROFILE_BLOCKS — never credentials,
# machine paths or network settings (that is what makes one safe to export and share). The
# lifecycle logic lives in `desktop/profiles.py`; these routes are the store's public face, and
# they always answer with the state the store ACCEPTED, so the UI can never display a profile
# the sanitiser refused.

def _profile_trade_counts() -> dict[str, int]:
    """Trades journaled while each profile was the active one — the metric the cards show."""
    import sqlite3

    path = Path(config_store.db_path())
    if not path.exists():
        return {}
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT profile_id, COUNT(*) FROM trade_journal "
                "WHERE profile_id IS NOT NULL AND profile_id <> '' GROUP BY profile_id").fetchall()
            return {str(row[0]): int(row[1]) for row in rows}
        finally:
            conn.close()
    except sqlite3.OperationalError:            # a database from before the column existed
        return {}


@router.get("/profiles")
async def profiles_get() -> dict[str, Any]:
    """Every profile with its live state: active, dirty (against the current setup), stats."""
    out = profiles_mod.state()
    counts = _profile_trade_counts()
    for row in out.get("items", []):
        row["trades"] = counts.get(row["id"], 0)
    return out


@router.post("/profiles")
async def profiles_post(payload: dict = Body(default={})) -> dict[str, Any]:
    """One write per call, actions in a fixed order (the layouts' pattern): save · apply · preview ·
    update · rename · duplicate · delete · restore_version · default · rules · export · import.

    `apply` without `dry_run` is the switch itself; with `dry_run` it is the preview (what would
    change, and which of it waits for the next engine start) and nothing is written.
    """
    payload = payload if isinstance(payload, dict) else {}
    out: Optional[dict[str, Any]] = None

    if isinstance(payload.get("save"), dict):
        entry = payload["save"]
        out = profiles_mod.save(str(entry.get("name") or ""), str(entry.get("description") or ""),
                                entry.get("tags") if isinstance(entry.get("tags"), list) else None,
                                entry.get("blocks") if isinstance(entry.get("blocks"), list) else None,
                                bool(entry.get("from_defaults")))
    if isinstance(payload.get("apply"), str) and payload["apply"]:
        out = profiles_mod.apply(payload["apply"], dry_run=bool(payload.get("dry_run")))
    if isinstance(payload.get("preview"), str) and payload["preview"]:
        out = profiles_mod.preview(payload["preview"])
    if isinstance(payload.get("update"), str) and payload["update"]:
        out = profiles_mod.update(payload["update"])
    if isinstance(payload.get("rename"), str) and payload.get("to"):
        out = profiles_mod.rename(payload["rename"], str(payload["to"]))
    if isinstance(payload.get("duplicate"), str) and payload["duplicate"]:
        out = profiles_mod.duplicate(payload["duplicate"], str(payload.get("name") or ""))
    if isinstance(payload.get("delete"), str) and payload["delete"]:
        out = profiles_mod.delete(payload["delete"])
    if isinstance(payload.get("restore_version"), dict):
        rv = payload["restore_version"]
        out = profiles_mod.restore_version(str(rv.get("id") or ""), int(rv.get("at") or 0))
    if "default" in payload or payload.get("auto_apply") is not None:
        out = profiles_mod.set_default(str(payload.get("default") or ""),
                                       payload.get("auto_apply") if payload.get("auto_apply") is not None else None)
    if isinstance(payload.get("rules"), dict) or payload.get("rules_enabled") is not None:
        out = profiles_mod.set_rules(payload.get("rules"), enabled=payload.get("rules_enabled"))
    if isinstance(payload.get("export"), str) and payload["export"]:
        filename, text, error = profiles_mod.export_bundle(payload["export"])
        out = {"action": "export", "filename": filename, "text": text, "error": error,
               **profiles_mod.state(), "ok": not error}
    if isinstance(payload.get("import"), dict):
        out = profiles_mod.import_bundle(payload["import"])

    if out is None:
        out = {**profiles_mod.state(), "ok": False,
               "error": "no recognised action — one of: save, apply, preview, update, "
                        "rename, duplicate, delete, restore_version, default, rules, export, import"}
    if out.get("ok") and isinstance(out.get("items"), list):
        counts = _profile_trade_counts()
        for row in out["items"]:
            row["trades"] = counts.get(row["id"], 0)
    return out


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
    # Where the open windows actually ARE (§128): a live position beats the store's copy, which a
    # drag may trail by the save throttle. The screen each window sits on is what the UI says out
    # loud ("on Monitor 2") and what makes "send it to the next monitor" a one-click command.
    geometry: dict[str, dict] = {}
    for wid in open_ids:
        try:
            rect = host.geometry(wid) if host is not None else None
        except Exception:
            logger.debug("window geometry read failed", exc_info=True)
            rect = None
        if not isinstance(rect, dict):
            continue
        try:
            row = {"x": int(rect.get("x")), "y": int(rect.get("y")),
                   "width": int(rect.get("width")), "height": int(rect.get("height"))}
        except (TypeError, ValueError):
            continue
        index = windows_mod.screen_index_of(screens, row["x"], row["y"])
        row["screen"] = index if index is not None else -1
        row["screen_label"] = labelled[index]["label"] if index is not None else ""
        geometry[wid] = row
    records = windows_mod.records()
    return {
        "native": host is not None,
        "host": getattr(host, "kind", "") if host is not None else "",
        "screens": labelled,
        "open": open_ids,
        "open_geometry": geometry,
        "stranded": windows_mod.stranded(records, screens, live=geometry) if host is not None else [],
        "windows": records,
        "max": config_store.WINDOWS_MAX,
    }


@router.get("/windows")
async def windows_get() -> dict[str, Any]:
    """The auxiliary-window state: screens, what is open, and the set a launch restores."""
    return _windows_state()


@router.post("/windows")
async def windows_post(payload: dict = Body(default={})) -> dict[str, Any]:
    """Open / close / focus / pin / reset one auxiliary window — the page's own window manager.
    A reset takes a window home: its stored geometry is dropped and it is re-placed on the primary
    screen (reopened there when open), which is the rescue for a window stranded on a monitor that
    is gone.

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
        preset = str(payload.get("preset") or "").strip().lower()
        if preset and preset in windows_mod.PRESETS and preset != "center":
            # Open it already snapped (the menu's "Open on Monitor 2, left half"): the requested
            # shape replaces the centred placement, on the screen place_aux just chose.
            rects = windows_mod.valid_screens(screens)
            landed = placement.get("screen")
            if isinstance(landed, int) and 0 <= landed < len(rects):
                placement.update(windows_mod.preset_rect(rects[landed], preset,
                                                         want_w=placement.get("width"),
                                                         want_h=placement.get("height")))
                placement["screen"] = landed
                placement["screen_label"] = windows_mod.screen_label(rects[landed], landed,
                                                                     rects[landed].get("scale"))
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

    if action == "move":
        # §128: send an existing window to a monitor, or snap it to a shape where it is. Works
        # whether the window is open (it moves now) or closed (its record is re-placed, so it opens
        # there next time) — and it is the command form of the OS drag that WebView2 cannot start.
        wid = str(payload.get("id") or "").strip().lower()
        if not wid:
            return {"ok": False, "action": action, "error": "which window?", **_windows_state()}
        record = next((r for r in windows_mod.records() if r["id"] == wid), None)
        if record is None:
            return {"ok": False, "action": action, "error": "no window with id %r" % wid,
                    **_windows_state()}
        try:
            screens = host.screens()
        except Exception:
            screens = []
        try:
            live = host.geometry(wid) or {}          # the live rect is the truth about "where it is"
        except Exception:
            logger.debug("window geometry read failed", exc_info=True)
            live = {}
        if isinstance(live, dict) and live:
            record = {**record, "x": live.get("x"), "y": live.get("y"),
                      "width": live.get("width") or record.get("width"),
                      "height": live.get("height") or record.get("height")}
        step = payload.get("step")
        preset = str(payload.get("preset") or "center")
        placed = windows_mod.move_placement(
            record, screens,
            screen_index=payload.get("screen") if isinstance(payload.get("screen"), int) else None,
            preset=preset,
            step=step if isinstance(step, int) else 0)
        if (isinstance(step, int) and step and "preset" not in payload
                and placed.get("screen") == windows_mod.screen_index_of(
                    screens, record.get("x"), record.get("y"))):
            # "Move it one monitor over" with nowhere to go (one screen, or a single-monitor
            # machine): doing nothing is the honest answer. The old shape resolved step cyclically
            # to the SAME screen and re-centred the window — a key that silently moves a hand-
            # placed window is worse than a key that does nothing.
            return {"ok": True, "action": action, "moved": "", "note": "already on that monitor",
                    **_windows_state()}
        if wid in set(_windows_state()["open"]):
            try:
                ok = bool(host.move(wid, placed["x"], placed["y"], placed["width"], placed["height"]))
            except Exception:
                logger.warning("window move failed", exc_info=True)
                ok = False
            if not ok:
                # The store is NOT written on a failed move: the window is where it was, and the
                # record must keep saying so.
                return {"ok": False, "action": action,
                        "error": "the window host could not move %r" % wid, **_windows_state()}
        windows_mod.add_record(placed)
        return {"ok": True, "action": action, "moved": wid, "screen_label": placed.get("screen_label", ""),
                **_windows_state()}

    if action == "arrange":
        # §128: the unplug rescue, for every window at once — each window on no screen is re-placed
        # on the primary (a live window moves there now, a closed one opens there next time).
        # Windows that still have a screen are left exactly alone. The stranded set comes from the
        # state, so it covers both a stale record and a live window the OS left off-desktop.
        try:
            screens = host.screens()
        except Exception:
            screens = []
        state = _windows_state()
        rows_by_id = {r["id"]: r for r in windows_mod.records()}
        open_now = set(state["open"])
        moved: list[str] = []
        for ordinal, wid in enumerate(state["stranded"]):
            record = rows_by_id.get(wid)
            if record is None:
                continue                     # an open window with no record is not ours to move
            live = state["open_geometry"].get(wid) or {}
            home = windows_mod.place_aux(
                {**record, "x": None, "y": None,
                 "width": live.get("width") or record.get("width"),
                 "height": live.get("height") or record.get("height")},
                screens, count=ordinal, screen_index=0)
            if wid in open_now:
                try:
                    if not host.move(wid, home["x"], home["y"], home["width"], home["height"]):
                        continue             # it stays open where it is; the record stays true
                except Exception:
                    logger.debug("window move failed during arrange", exc_info=True)
                    continue
            windows_mod.add_record(home)
            moved.append(wid)
        return {"ok": True, "action": action, "moved": moved,
                "note": ("brought %d window(s) home" % len(moved)) if moved else "nothing was stranded",
                **_windows_state()}

    if action == "reset":
        # T2: take a window home — geometry dropped, re-placed on the primary screen, reopened
        # there when it was open. This is the in-app rescue for the field's classic failure:
        # "the window became unreachable" after a monitor change.
        wid = str(payload.get("id") or "").strip().lower()
        rows = windows_mod.records()
        record = next((r for r in rows if r["id"] == wid), None)
        if record is None:
            return {"ok": False, "action": action, "error": "no window with id %r" % wid,
                    **_windows_state()}
        try:
            screens = host.screens()
        except Exception:
            screens = []
        home = windows_mod.place_aux({**record, "screen_key": None, "x": None, "y": None},
                                     screens, count=1, screen_index=0)
        was_open = wid in set(host.open_ids() or [])
        if was_open:
            try:
                host.close(wid)
            except Exception:
                logger.debug("window close failed during reset", exc_info=True)
            windows_mod.drop_record(wid)
        windows_mod.add_record(home)
        try:
            host.open(home)
        except Exception as exc:
            logger.warning("window reset open failed", exc_info=True)
            return {"ok": False, "action": action,
                    "error": "the window host refused: %s" % exc, **_windows_state()}
        return {"ok": True, "action": action, "reset": wid,
                "screen_label": home.get("screen_label", ""), **_windows_state()}

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
            "error": "unknown action %r (open, close, focus, ontop, reset, close_all)" % action,
            **_windows_state()}


# ──────────────────────────────────────────────────────────────
# Help Centre (§79)
# ──────────────────────────────────────────────────────────────

@router.get("/help")
async def help_report() -> dict[str, Any]:
    """Everything the in-app help system cannot invent: the facts, the credits and the system check.

    The topic corpus and the search engine are front-end (desktop/ui/help-data.js, help-search.js);
    what lives here is the program's own truth — name, version, licence, folders — plus the
    configuration errors and irregularities the Simple interface warns about. Read-only: it never
    starts an engine, never touches the network and never writes.
    """
    from orderflow_system.desktop import help as help_mod

    return help_mod.report()


@router.post("/help")
async def help_prefs(payload: dict = Body(default={})) -> dict[str, Any]:
    """Persist the Help Centre's preferences (patched, validated by the store).

    Body: `{mode?: "advanced"|"simple", dock?: "taskbar"|"floating"|"off", recents?: [ids],
    dismissed?: [check ids]}` — omitted keys keep their stored value, a value outside the allowed set
    is ignored rather than resetting what is stored, and both lists are bounded by the store. The
    answer is the stored block, so the UI adopts what was saved rather than what it sent.
    """
    patch: dict[str, Any] = {}
    mode = str(payload.get("mode") or "").strip().lower()
    if mode in ("advanced", "simple"):
        patch["mode"] = mode
    dock = str(payload.get("dock") or "").strip().lower()
    if dock in ("taskbar", "floating", "off"):
        patch["dock"] = dock
    if isinstance(payload.get("recents"), list):
        patch["recents"] = [str(t) for t in payload["recents"]]
    if isinstance(payload.get("dismissed"), list):
        patch["dismissed"] = [str(t) for t in payload["dismissed"]]
    if not patch:
        return {"ok": False, "error": "nothing to save (mode, dock, recents, dismissed)",
                "help": config_store.load_config().get("help", {})}
    saved = config_store.merge_config({"help": patch})
    return {"ok": True, "help": saved.get("help", {}),
            "config_path": str(config_store.config_path())}
