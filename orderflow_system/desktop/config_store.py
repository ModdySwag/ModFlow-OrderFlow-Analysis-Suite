"""
Desktop configuration store.

A single JSON file in the per-user config directory holds everything the GUI can
change at runtime, so users never have to edit Python source:

    Windows : %APPDATA%\\OrderFlowAnalysisPro\\config.json
    macOS   : ~/Library/Application Support/OrderFlowAnalysisPro/config.json
    Linux   : ~/.config/OrderFlowAnalysisPro/config.json

The store is intentionally dependency-free (stdlib only) so it works on every
platform without extra wheels.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from orderflow_system.config.settings import CRYPTO_MAJORS

logger = logging.getLogger(__name__)

APP_DIR_NAME = "OrderFlowAnalysisPro"

#: Module identifiers for studies (`name` in a the suite's definition).
_STUDY_NAME_RE = __import__("re").compile(r"^[A-Za-z][A-Za-z0-9_-]{1,40}$")


# ──────────────────────────────────────────────────────────────
# Terminal layouts — the shell's arrangement store
# ──────────────────────────────────────────────────────────────
#
# One entry per named arrangement (mode, screen, theme, tabs, widgets) plus the mode the app boots
# into. Ids are slugs; a widget names an existing view section by the same slug the markup uses, so
# the store needs no copy of the view list — a widget for a view that is not there is simply not
# drawn (the shell drops it and says so).

LAYOUT_ID_RE = __import__("re").compile(r"^[a-z0-9][a-z0-9_-]{0,23}$")
LAYOUT_VIEW_RE = __import__("re").compile(r"^[a-z][a-z0-9_-]{0,23}$")
#: A widget's link is "<symbol group>/<timeframe group>", either side optional (A-D). It is stored as
#: written so the shell can show it back verbatim; anything that is not that shape is dropped.
LAYOUT_LINK_RE = __import__("re").compile(r"^[A-D]?(/[A-D]?)?$")
LAYOUT_MODES = ("classic", "terminal")
LAYOUT_THEMES = ("dark", "light")
#: The widget grid, in cells. `desktop/ui/shell.js` lays widgets out on these same numbers.
LAYOUT_GRID_COLS = 12
LAYOUT_GRID_ROWS = 8
LAYOUT_MAX_ITEMS = 24
LAYOUT_MAX_TABS = 12
LAYOUT_MAX_WIDGETS = 24


# ──────────────────────────────────────────────────────────────
# Platform paths
# ──────────────────────────────────────────────────────────────

def config_dir() -> Path:
    """Per-user, per-platform config directory (created on demand)."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.json"


def log_path() -> Path:
    return config_dir() / "orderflow.log"


def db_path() -> Path:
    """The per-user database (never the repo, which may be read-only if installed).

    One-time migration: an older install kept `orderflow_data.db` in the working
    directory, so if this user has one and the per-user copy is still empty, copy
    it across once — otherwise a fresh desktop start would look like the history
    vanished.
    """
    target = config_dir() / "orderflow_data.db"
    try:
        legacy = Path("orderflow_data.db")
        thin = target.is_file() is False or target.stat().st_size < 1_000_000
        if thin and legacy.is_file() and legacy.stat().st_size > 1_000_000:
            import shutil

            shutil.copy2(legacy, target)
            logger.info("Migrated %s → %s (%.1f MB)", legacy, target, legacy.stat().st_size / 1e6)
    except Exception:                              # pragma: no cover - never break startup
        logger.debug("legacy DB migration skipped", exc_info=True)
    return target


# ──────────────────────────────────────────────────────────────
# Defaults — derived from the repo's own settings module
# ──────────────────────────────────────────────────────────────

#: Instruments Bybit perpetuals actually list (validated at runtime against the
#: public instruments-info endpoint; this is only the offline fallback set).
#: Derived from the instrument matrix: one list to maintain, not two to keep in sync.
BYBIT_FALLBACK_SYMBOLS = ["BTCUSDT", *CRYPTO_MAJORS]

#: Asset classes, used by the GUI to group instruments.
ASSET_CLASS = {
    "NAS100USDT": "Indices", "SP500": "Indices", "DJ30": "Indices",
    "UK100": "Indices", "DAX40": "Indices", "NIKKEI225": "Indices",
    "CAC40": "Indices", "ASX200": "Indices", "HK50": "Indices",
    "XAUUSDT": "Metals", "XAGUSD": "Metals",
    "USOIL": "Energy", "UKOIL": "Energy",
    "EURUSD": "Forex", "GBPUSD": "Forex", "USDJPY": "Forex", "AUDUSD": "Forex",
    "USDCAD": "Forex", "USDCHF": "Forex", "NZDUSD": "Forex", "EURGBP": "Forex",
    "EURJPY": "Forex", "GBPJPY": "Forex",
    "AAPL": "Stocks", "TSLA": "Stocks", "AMZN": "Stocks", "MSFT": "Stocks",
    "NVDA": "Stocks", "META": "Stocks", "GOOGL": "Stocks",
    "BTCUSDT": "Crypto",
}

#: Every crypto major is Bybit-listed, so tag them all as Crypto in one go.
ASSET_CLASS.update({sym: "Crypto" for sym in BYBIT_FALLBACK_SYMBOLS})


def default_config() -> dict[str, Any]:
    """Build the default config straight from the repo's settings module."""
    from orderflow_system.config.settings import get_all_configs, MT5, ALPACA as ALPACA_SETTINGS

    instruments = []
    for cfg in get_all_configs():
        sym = cfg.instrument.value
        instruments.append({
            "symbol": sym,
            "asset_class": ASSET_CLASS.get(sym, "Other"),
            "enabled": sym in ("BTCUSDT",),          # sane first-run default
            "mt5_symbol": MT5.symbols.get(sym, ""),
            "alpaca_symbol": ALPACA_SETTINGS.symbols.get(sym, ""),
            "bybit_symbol": sym if sym in BYBIT_FALLBACK_SYMBOLS else "",
            "tick_size": cfg.tick_size,
            "patterns": {
                "absorption": {
                    "min_aggressive_volume": cfg.absorption.min_aggressive_volume,
                    "max_price_displacement_ticks": cfg.absorption.max_price_displacement_ticks,
                    "min_attempts": cfg.absorption.min_attempts,
                },
                "initiative": {
                    "min_delta_threshold": cfg.initiative.min_delta_threshold,
                    "volume_acceleration_min": cfg.initiative.volume_acceleration_min,
                    "min_price_displacement_ticks": cfg.initiative.min_price_displacement_ticks,
                },
                "sweep": {
                    "min_levels_swept": cfg.sweep.min_levels_swept,
                    "thin_book_threshold": cfg.sweep.thin_book_threshold,
                },
                "exhaustion": {
                    "min_bars_declining": cfg.exhaustion.min_bars_declining,
                    "volume_decline_pct": cfg.exhaustion.volume_decline_pct,
                },
                "divergence": {
                    "lookback_bars": cfg.divergence.lookback_bars,
                    "delta_failure_pct": cfg.divergence.delta_failure_pct,
                },
            },
        })

    return {
        "version": 1,
        "data_source": "bybit",            # mt5 | bybit | both
        "instruments": instruments,
        "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
        # Optional alert channels. All free: ntfy needs no account at all (pick a
        # topic name), email needs any mailbox with an app password.
        "notify": {
            "ntfy": {"enabled": False, "server": "https://ntfy.sh", "topic": ""},
            "email": {"enabled": False, "host": "", "port": 587, "username": "",
                      "password": "", "to": "", "from": "", "use_tls": True},
        },
        # Free market context (no keys): venue funding/open interest/long-short
        # ratio, Fear & Greed, and RSS headlines.
        "context": {"enabled": True, "positioning": True, "fear_greed": True,
                    "news": True, "news_url": "", "news_limit": 8},
        "dashboard": {"host": "127.0.0.1", "port": 8080},
        # Third-party platform bridge. the DTC platform is reachable over its DTC server, so its
        # connection details live here (like the Alpaca keys: per-user config, never in the
        # repo, never in logs). the reference platform has no external API — nothing to store for it.
        "platforms": {
            "sierra": {"enabled": False, "host": "127.0.0.1", "port": 11099,
                       "username": "", "password": "", "use_tls": False, "symbol": "",
                       "plan": "free", "integrated": False},
        },
        # Indicator modules (the suite's indicator contract). `active` is what draws on the
        # chart; `custom` holds modules pasted through the Studies view, which the app
        # hands back to the browser on load.
        "studies": {"active": [], "custom": [], "data_box": True},
        "workspaces": {},
        # Terminal layouts: the widget arrangement for the shell's terminal mode — named, per screen
        # and per theme, with tabs. Same atomic write + sanitiser pattern as every other block, and
        # the config file stays the single store (browser storage is never the source of truth).
        "layouts": {"mode": "classic", "active": "", "items": {}},
        # Drawings, per view+symbol, in data space (epoch seconds + price). The shape mirrors the
        # reference program's own drawingSettings so the two models stay comparable.
        "drawings": {},
        "markers": {},
        "ofx": {"symbol": "", "R": 4.0, "stack": 3, "lambda_ms": 500, "text_px": 45, "sweep_c": 1.15,
                "min_block": 0.0, "va_pct": 0.7},
        "risk": {"signal_cooldown_seconds": 30.0, "min_composite_score": 40.0},
        "atlas": {
            "extras_enabled": True,          # extra Bybit streams: 200-level book,
                                             # liquidations, block-trade flags
            "heatmap": {
                "bucket_ms": 1000, "max_columns": 900, "wall_quantile": 0.97,
                "pull_pct": 0.6, "pull_window_ms": 3000, "stack_pct": 1.5,
                "upper_cutoff_pct": 5.0,     # colour saturates at this top share (the reference layout)
            },
            "tape": {
                "big_quantile": 0.99, "big_min_size": 0.0, "block_multiple": 3.0,
                "sweep_levels": 5, "sweep_max_ms": 120, "sweep_min_size": 0.0,
                "sweep_min_aggressors": 1, "sweep_min_range_ticks": 0.0,
                "iceberg_min_fills": 4, "iceberg_min_total": 0.0, "iceberg_min_duration_s": 0.0,
                "stoprun_ticks": 12.0, "stoprun_ms": 3000,
                "stoprun_min_volume": 0.0, "stoprun_min_prints": 1,
                "reassembly_ms": 80, "zone_ticks": 100.0,
            },
            "cvd": {"bucket_ms": 5000, "divergence_lookback": 24, "divergence_min_ticks": 6.0,
                    "pro_min_size": 0.0, "pro_max_size": 0.0,     # CVD Pro size band (0 = off)
                    "pro_bands": []},              # CVD Pro (Multi): up to 5 size buckets
            "market_profile": {"bracket_minutes": 30, "value_area_pct": 0.70},
            "webhook_url": "",                 # rules with a "webhook" channel POST here
            "imbalance": {"rate_pct": 150.0, "window_s": 300, "min_volume": 0.01, "min_levels": 3},
            # VWAP suite (session + anchored + sigma bands) — the reference platform's Order Flow VWAP
            "vwap": {"window_s": 86400, "bands": [1, 2, 3], "cross_min_ticks": 1.0},
            # Numbers-Bars pack: the imbalance convention, its ratio, and the print-size
            # filter applied while building bars (0 = keep every print).
            "footprint": {"min_print_size": 0.0, "imbalance_mode": "same_price",
                          "imbalance_threshold": 3.0, "equal_tolerance": 0.0,
                          "show_equal": True, "show_extremes": True},
            "dots": {"window_ms": 300000, "cluster_ms": 250, "min_size": 0.0},
            "correlation": {"bucket_ms": 60000, "window": 120, "min_samples": 10, "top": 12},
            # trade detector: executions that eat resting depth, and refills of those levels
            "detector": {"min_share": 0.25, "size_mult": 4.0, "resting_mult": 8.0,
                         "refill_pct": 0.7, "refill_ms": 4000},
            # scanner: cross-instrument ranking window (seconds)
            "scanner_window_s": 900,
            # participants' intent: DOM pressure weighting + training window (sensible defaults)
            "intent": {"levels": 10, "decay": 3.0, "threshold_pct": 80.0, "training_min": 5,
                       "absorb_window_s": 20.0, "absorb_ref_ticks": 8.0,
                       "spoof_near_ticks": 10.0, "spoof_size_mult": 3.0,
                       "trap_ticks": 3.0, "trap_window_s": 120.0, "trap_reclaim_s": 60.0},
            "history": {"enabled": True},     # every detection appended to SQLite
            "telegram": {"enabled": True},    # route rule alerts to Telegram when configured
            "alert_rules": [],               # empty → the reference-style default rule set
        },
        # Alpaca Markets (optional): a real US brokerage account as a data + execution
        # source. Free paper trading needs only an email address; keys are per
        # environment (paper keys do not work against the live host).
        "alpaca": {
            "enabled": False, "paper": True, "key_id": "", "secret": "",
            "feed": "iex",                 # iex | sip | delayed_sip (entitlement)
            "snapshot_seconds": 5.0,
            "view_symbols": ["AAPL", "MSFT", "NVDA", "SPY", "QQQ"],
        },
        "mt5": {
            "login": 0, "password": "", "server": "", "path": "",
            "poll_interval_ms": 100, "enable_book": True, "download_history_days": 3,
        },
        "search": {
            # the palette remembers what you actually look at (GUI-only)
            "recents": [],                 # newest first, capped below
            "pins": [],                    # pinned to the top of every search
            "default_view": "orderflow",   # where Enter lands for a symbol
            "sort": "relevance",
        },
        "watchlist": [],                   # symbols kept for the multi-symbol views
        "logging": {"level": "INFO"},
        # GUI-only flags. The engine never reads these; they exist so the front end
        # can remember what the user already saw without a second storage file.
        "ui": {
            # "not now" on the Alpaca banner — persisted so the dismissal survives a
            # reload, and cleared at the next start while the account is unlinked
            "banner_dismissed_alpaca": False,
            # where the setup assistant should resume (step index, 0 = start)
            "wizard_resume_step": 0,
            # The shell's appearance (theme.js, themes/*.css). The config is the record; the browser
            # keeps a mirror purely so the first paint is already the right theme.
            "theme": "dark",            # dark | light | contrast
            "accent": "cobalt",         # the eight Windows accents
            "density": "comfortable",   # comfortable | compact | dense
        },
    }


# ──────────────────────────────────────────────────────────────
# Load / save
# ──────────────────────────────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge ``override`` onto a copy of ``base``."""
    out = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config() -> dict[str, Any]:
    """Load config.json, merged over defaults. Never raises on bad input."""
    defaults = default_config()
    path = config_path()
    if not path.is_file():
        return defaults
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaults
    if not isinstance(raw, dict):
        return defaults
    return _deep_merge(defaults, raw)


def save_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Validate + persist config. Returns the sanitised config that was stored.

    The merge base is the DEFAULTS, so this writes what it is given and drops what it is not —
    which is what a caller that computes a whole block needs in order to remove a key from it
    (the layout delete path depends on exactly that). For a partial write from outside, use
    merge_config() below, which patches over whatever is stored instead of resetting it.
    """
    clean = _sanitise(_deep_merge(default_config(), cfg))
    path = config_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    tmp.replace(path)          # atomic on Windows + macOS
    return clean


def merge_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Patch the stored config: keys the body omits keep their current values.

    This is the write the settings API uses. save_config() merges over the defaults, so a partial POST
    used to reset every key it did not mention — measured: `{"ui": {"banner_dismissed_alpaca": true}}`
    took `search.default_view` and `context.fear_greed` back to their factory values. Merging over what
    is on disk first fixes that while leaving block-level removal (a layout delete) to save_config.
    """
    return save_config(_deep_merge(load_config(), cfg))


def _block(cfg: dict[str, Any], key: str) -> dict[str, Any]:
    """Fetch a config block, replacing anything that is not a mapping.

    A hand-edited file with `"risk": 5` (or a POST that sends a string) must never
    make saving crash — the store is the only writer of the user's settings.
    """
    value = cfg.get(key)
    if not isinstance(value, dict):
        value = {}
        cfg[key] = value
    return value


def _clamp(value: Any, lo: float, hi: float, default: float) -> float:
    """A number inside its bounds, or the default. The store's only numeric coercion."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, out))


# ── terminal layouts ──────────────────────────────────────────────────────────────────────────

def _clean_layout(raw_id: str, entry: Any) -> dict[str, Any] | None:
    """One layout as the store will keep it, or None when it cannot be identified at all."""
    if not isinstance(entry, dict):
        return None
    layout_id = str(entry.get("id") or raw_id or "").strip().lower()
    if not LAYOUT_ID_RE.match(layout_id):
        return None                                     # an unidentifiable layout is not stored
    mode = str(entry.get("mode") or "terminal").lower()
    theme = str(entry.get("theme") or "dark").lower()
    tabs_in = entry.get("tabs")

    tabs: list[dict[str, Any]] = []
    used: set[str] = set()
    for index, tab in enumerate(tabs_in if isinstance(tabs_in, list) else []):
        if len(tabs) >= LAYOUT_MAX_TABS:
            break
        if not isinstance(tab, dict):
            continue
        tab_id = str(tab.get("id") or "").strip().lower()
        if not LAYOUT_ID_RE.match(tab_id) or tab_id in used:
            tab_id = "t%d" % (index + 1)
            while tab_id in used:
                tab_id += "x"
        used.add(tab_id)

        widgets: list[dict[str, Any]] = []
        for widget in (tab.get("widgets") if isinstance(tab.get("widgets"), list) else []):
            if len(widgets) >= LAYOUT_MAX_WIDGETS:
                break
            if not isinstance(widget, dict):
                continue
            view = str(widget.get("view") or "").strip().lower()
            if not LAYOUT_VIEW_RE.match(view):
                continue
            w = int(_clamp(widget.get("w", 6), 1, LAYOUT_GRID_COLS, 6))
            h = int(_clamp(widget.get("h", 4), 1, LAYOUT_GRID_ROWS, 4))
            # clamped in two phases, x after w: a widget can never be stored hanging off the grid
            x = int(_clamp(widget.get("x", 0), 0, LAYOUT_GRID_COLS - w, 0))
            y = int(_clamp(widget.get("y", 0), 0, LAYOUT_GRID_ROWS - h, 0))
            link = str(widget.get("link") or "").strip().upper()[:16]
            if link == "/" or not LAYOUT_LINK_RE.match(link):
                link = ""            # only "<symbol group>/<timeframe group>" is a link
            settings = widget.get("settings") if isinstance(widget.get("settings"), dict) else {}
            clean_settings: dict[str, Any] = {}
            for key, value in list(settings.items())[:24]:
                key = str(key)[:32]
                if isinstance(value, bool) or isinstance(value, (int, float)):
                    clean_settings[key] = value
                elif isinstance(value, str):
                    clean_settings[key] = value[:120]
            widgets.append({"view": view, "x": x, "y": y, "w": w, "h": h,
                            "link": link,
                            "settings": clean_settings})
        tabs.append({"id": tab_id,
                     "name": str(tab.get("name") or "").strip()[:40] or ("Tab %d" % (index + 1)),
                     "widgets": widgets})
    if not tabs:
        tabs = [{"id": "main", "name": "Main", "widgets": []}]

    return {
        "id": layout_id,
        "name": str(entry.get("name") or "").strip()[:40] or "Layout",
        "mode": mode if mode in LAYOUT_MODES else "terminal",
        "screen_key": str(entry.get("screen_key") or "").strip()[:24],
        "theme": theme if theme in LAYOUT_THEMES else "dark",
        "saved": int(_clamp(entry.get("saved", 0), 0, 9_999_999_999_999, 0)),
        "tabs": tabs,
    }


def _sanitise_layouts(cfg: dict[str, Any]) -> None:
    """Clamp the layout block: identified ids only, capped, and the active id must exist."""
    block = _block(cfg, "layouts")
    mode = str(block.get("mode") or "classic").lower()
    block["mode"] = mode if mode in LAYOUT_MODES else "classic"

    raw = block.get("items")
    if isinstance(raw, dict):
        pairs = [(str(k), v) for k, v in list(raw.items())[:LAYOUT_MAX_ITEMS]]
    elif isinstance(raw, list):                       # an exported bundle round-tripped as a list
        pairs = [("", v) for v in raw[:LAYOUT_MAX_ITEMS]]
    else:
        pairs = []
    items: dict[str, Any] = {}
    for raw_id, entry in pairs:
        layout = _clean_layout(raw_id, entry)
        if layout is not None:
            items[layout["id"]] = layout
    block["items"] = items
    active = str(block.get("active") or "").strip().lower()
    block["active"] = active if active in items else ""


def _sanitise(cfg: dict[str, Any]) -> dict[str, Any]:
    """Clamp/coerce user input so a bad value can never kill the engine."""
    cfg["data_source"] = str(cfg.get("data_source", "bybit")).lower()

    # Platform bridge: connection details are the user's own local values. Nothing here is
    # ever echoed back to the UI (the GET masks the password), and nothing personal belongs
    # in this block — a test asserts the catalogue carries no PII either.
    plat = _block(cfg, "platforms")
    sierra = _block(plat, "sierra")
    sierra["enabled"] = bool(sierra.get("enabled", False))
    sierra["host"] = str(sierra.get("host", "127.0.0.1") or "127.0.0.1").strip()[:120]
    try:
        sierra["port"] = max(1, min(65535, int(sierra.get("port", 11099) or 11099)))
    except (TypeError, ValueError):
        sierra["port"] = 11099
    sierra["username"] = str(sierra.get("username", "") or "").strip()[:120]
    sierra["password"] = str(sierra.get("password", "") or "")[:200]
    sierra["use_tls"] = bool(sierra.get("use_tls", False))
    sierra["symbol"] = str(sierra.get("symbol", "") or "").strip().upper()[:24]

    # Studies: names are module identifiers, parameters are user scalars, and a pasted
    # module is source text the browser validates before running. Nothing here executes
    # on the server.
    studies = _block(cfg, "studies")
    active = studies.get("active")
    if not isinstance(active, list):
        active = []
    clean_active = []
    for entry in active[:40]:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "") or "").strip()
        if not _STUDY_NAME_RE.match(name):
            continue
        params = entry.get("params") if isinstance(entry.get("params"), dict) else {}
        clean_params = {}
        for key, value in list(params.items())[:40]:
            key = str(key)[:40]
            if isinstance(value, bool) or isinstance(value, (int, float)):
                clean_params[key] = value
            elif isinstance(value, str):
                clean_params[key] = value[:120]
        clean_active.append({"name": name, "params": clean_params,
                             "visible": bool(entry.get("visible", True))})
    studies["active"] = clean_active

    custom = studies.get("custom")
    if not isinstance(custom, list):
        custom = []
    clean_custom = []
    for entry in custom[:20]:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "") or "").strip()[:40]
        source = str(entry.get("source", "") or "")[:20000]
        if not source or not name:
            continue
        clean_custom.append({"name": name, "source": source, "enabled": bool(entry.get("enabled", True))})
    studies["custom"] = clean_custom
    studies["data_box"] = bool(studies.get("data_box", True))

    ofx = _block(cfg, "ofx")

    ofx["symbol"] = str(ofx.get("symbol", "") or "").strip().upper()[:24]
    ofx["R"] = round(_clamp(ofx.get("R", 4.0), 1.5, 20.0, 4.0), 2)
    ofx["stack"] = int(_clamp(ofx.get("stack", 3), 2, 8, 3))
    ofx["lambda_ms"] = int(_clamp(ofx.get("lambda_ms", 500), 100, 5000, 500))
    ofx["text_px"] = int(_clamp(ofx.get("text_px", 45), 20, 120, 45))
    ofx["sweep_c"] = round(_clamp(ofx.get("sweep_c", 1.15), 0.2, 4.0, 1.15), 2)

    spaces = _block(cfg, "workspaces")
    clean_spaces: dict[str, Any] = {}
    for name, entry in list(spaces.items())[:20]:
        key = str(name).strip()[:32]
        if not key or not isinstance(entry, dict):
            continue
        view = str(entry.get("view", "") or "")[:24]
        ofx_in = entry.get("ofx") if isinstance(entry.get("ofx"), dict) else {}
        clean_spaces[key] = {
            "view": view,
            "ofx": {
                "symbol": str(ofx_in.get("symbol", "") or "").upper()[:24],
                "R": round(_clamp(ofx_in.get("R", 4.0), 1.5, 20.0, 4.0), 2),
                "stack": int(_clamp(ofx_in.get("stack", 3), 2, 8, 3)),
                "lambda": int(_clamp(ofx_in.get("lambda", 500), 100, 5000, 500)),
                "textPx": int(_clamp(ofx_in.get("textPx", 45), 20, 120, 45)),
                "sweepC": round(_clamp(ofx_in.get("sweepC", 1.15), 0.2, 4.0, 1.15), 2),
                "vaPct": round(_clamp(ofx_in.get("vaPct", 0.7), 0.5, 0.95, 0.7), 2),
                "minBlock": round(_clamp(ofx_in.get("minBlock", 0.0), 0.0, 1000000.0, 0.0), 2),
            },
            "saved": int(_clamp(entry.get("saved", 0), 0, 9_999_999_999_999, 0)),
        }
    cfg["workspaces"] = clean_spaces

    # ── terminal layouts: identified ids, capped tabs/widgets, coordinates inside the grid ────────
    _sanitise_layouts(cfg)

    # ── drawings: validated, capped, pixel-free (they live in data space) ──────────────────
    DRAW_KINDS = {"line", "ray", "hline", "vline", "rect", "ellipse", "channel", "fib", "text", "measure"}
    DRAW_EXTEND = {"none", "left", "right", "both"}
    DRAW_DASH = {"solid", "dashed", "dotted"}

    def _colour(value: Any, default: str) -> str:
        text = str(value or "").strip()[:32]
        if re.match(r"^#[0-9a-fA-F]{3,8}$", text):
            return text
        if re.match(r"^rgba?\([0-9.,\s]+\)$", text):
            return text
        return default

    def _point(node: Any) -> dict[str, float] | None:
        if not isinstance(node, dict):
            return None
        try:
            t_ = float(node.get("t"))
            p_ = float(node.get("p"))
        except (TypeError, ValueError):
            return None
        if not (-1e12 < t_ < 1e12 and -1e12 < p_ < 1e12):
            return None
        return {"t": round(t_, 3), "p": round(p_, 6)}

    spaces = cfg.get("drawings")
    clean_drawings: dict[str, Any] = {}
    if isinstance(spaces, dict):
        for key, entry in list(spaces.items())[:64]:
            slot = str(key).strip()[:64]
            if not slot or not isinstance(entry, dict):
                continue
            rows = []
            for item in (entry.get("drawings") or [])[:500]:
                if not isinstance(item, dict) or item.get("kind") not in DRAW_KINDS:
                    continue
                a = _point(item.get("a"))
                b = _point(item.get("b")) or a
                if not a:
                    continue
                style_in = item.get("style") if isinstance(item.get("style"), dict) else {}
                highlight_in = item.get("highlight") if isinstance(item.get("highlight"), dict) else {}
                rows.append({
                    "id": str(item.get("id") or "")[:24],
                    "kind": item["kind"],
                    "a": a,
                    "b": b,
                    "text": str(item.get("text") or "")[:240],
                    "style": {
                        "line": _colour(style_in.get("line"), "#4f8cff"),
                        "fill": _colour(style_in.get("fill"), "rgba(79,140,255,.14)"),
                        "width": int(_clamp(style_in.get("width", 2), 1, 8, 2)),
                        "dash": style_in.get("dash") if style_in.get("dash") in DRAW_DASH else "solid",
                        "fontSize": int(_clamp(style_in.get("fontSize", 12), 8, 28, 12)),
                    },
                    "highlight": {"price": bool(highlight_in.get("price")), "time": bool(highlight_in.get("time"))},
                    "extend": item.get("extend") if item.get("extend") in DRAW_EXTEND else "none",
                    "offset": int(_clamp(item.get("offset", 40), 6, 400, 40)),
                })
            default_style_in = entry.get("style") if isinstance(entry.get("style"), dict) else {}
            clean_drawings[slot] = {
                "symbol": str(entry.get("symbol") or "").upper()[:24],
                "view": str(entry.get("view") or "")[:24],
                "hidden": bool(entry.get("hidden")),
                "single": bool(entry.get("single")),
                "style": {
                    "line": _colour(default_style_in.get("line"), "#4f8cff"),
                    "fill": _colour(default_style_in.get("fill"), "rgba(79,140,255,.14)"),
                    "width": int(_clamp(default_style_in.get("width", 2), 1, 8, 2)),
                    "dash": default_style_in.get("dash") if default_style_in.get("dash") in DRAW_DASH else "solid",
                    "fontSize": int(_clamp(default_style_in.get("fontSize", 12), 8, 28, 12)),
                },
                "drawings": rows,
            }
    cfg["drawings"] = clean_drawings

    # ── markers: the heatmap's pinned levels, per symbol, in data space (never pixels) ────────────
    marker_spaces = cfg.get("markers")
    clean_markers: dict[str, Any] = {}
    if isinstance(marker_spaces, dict):
        for key, entry in list(marker_spaces.items())[:64]:
            slot = str(key).strip().upper()[:24]
            if not slot or not isinstance(entry, dict):
                continue
            rows = []
            for item in (entry.get("markers") or [])[:500]:
                if not isinstance(item, dict):
                    continue
                try:
                    price = float(item.get("price"))
                except (TypeError, ValueError):
                    continue
                if not (0.0 < price < 1e12):
                    continue
                try:
                    bucket = int(float(item.get("bucket") or 0))
                except (TypeError, ValueError):
                    bucket = 0
                try:
                    size = round(float(item.get("size") or 0), 8)
                except (TypeError, ValueError):
                    size = 0.0
                rows.append({
                    "price": round(price, 6),
                    "bucket": bucket if 0 < bucket < 1e12 else 0,
                    "size": size if 0 < size < 1e12 else 0.0,
                    "note": str(item.get("note") or "")[:120],
                })
            if rows:
                clean_markers[slot] = {"markers": rows}
    cfg["markers"] = clean_markers
    ofx["min_block"] = round(_clamp(ofx.get("min_block", 0.0), 0.0, 1_000_000.0, 0.0), 2)
    ofx["va_pct"] = round(_clamp(ofx.get("va_pct", 0.7), 0.5, 0.95, 0.7), 2)
    if cfg["data_source"] not in ("mt5", "bybit", "both", "alpaca", "all"):
        cfg["data_source"] = "bybit"

    sierra_block = (cfg.get("platforms") or {}).get("sierra")
    if isinstance(sierra_block, dict):
        sierra_block["plan"] = str(sierra_block.get("plan") or "free").lower()
        if sierra_block["plan"] not in ("free", "p3", "p5", "p10", "p11", "p12"):
            sierra_block["plan"] = "free"
        sierra_block["integrated"] = bool(sierra_block.get("integrated"))

    dash = _block(cfg, "dashboard")
    try:
        port = int(dash.get("port", 8080))
    except (TypeError, ValueError):
        port = 8080
    dash["port"] = min(max(port, 1024), 65535)
    dash["host"] = "127.0.0.1"

    tg = _block(cfg, "telegram")
    tg["bot_token"] = str(tg.get("bot_token", "") or "").strip()
    tg["chat_id"] = str(tg.get("chat_id", "") or "").strip()

    # a hand-edited file could hold anything here; the engine needs a list of mappings
    cfg["instruments"] = [i for i in (cfg.get("instruments") or []) if isinstance(i, dict)]
    for inst in cfg["instruments"]:
        inst["symbol"] = str(inst.get("symbol", "")).upper()
        inst["enabled"] = bool(inst.get("enabled", False))
        try:
            inst["tick_size"] = float(inst.get("tick_size", 0.1))
        except (TypeError, ValueError):
            inst["tick_size"] = 0.1

    risk = _block(cfg, "risk")
    for key, default in (("signal_cooldown_seconds", 30.0), ("min_composite_score", 40.0)):
        try:
            risk[key] = float(risk.get(key, default))
        except (TypeError, ValueError):
            risk[key] = default

    search = _block(cfg, "search")
    search["recents"] = [str(s).strip().upper() for s in (search.get("recents") or [])
                         if isinstance(s, str) and s.strip()][:12]
    search["pins"] = [str(s).strip().upper() for s in (search.get("pins") or [])
                      if isinstance(s, str) and s.strip()][:30]
    view = str(search.get("default_view") or "orderflow")
    search["default_view"] = view if view in ("orderflow", "chart", "tape", "heatmap", "cvd", "profile") else "orderflow"

    fp = _block(_block(cfg, "atlas"), "footprint")
    fp["min_print_size"] = max(0.0, float(fp.get("min_print_size", 0.0) or 0.0))
    mode = str(fp.get("imbalance_mode", "same_price") or "same_price").lower()
    fp["imbalance_mode"] = mode if mode in ("same_price", "diagonal") else "same_price"
    try:
        fp["imbalance_threshold"] = min(50.0, max(1.0, float(fp.get("imbalance_threshold", 3.0) or 3.0)))
    except (TypeError, ValueError):
        fp["imbalance_threshold"] = 3.0
    try:
        fp["equal_tolerance"] = min(1.0, max(0.0, float(fp.get("equal_tolerance", 0.0) or 0.0)))
    except (TypeError, ValueError):
        fp["equal_tolerance"] = 0.0
    fp["show_equal"] = bool(fp.get("show_equal", True))
    fp["show_extremes"] = bool(fp.get("show_extremes", True))
    sort = str(search.get("sort") or "relevance")
    search["sort"] = sort if sort in ("relevance", "symbol", "name", "last", "chg", "volume", "feed") else "relevance"

    wl = cfg.get("watchlist")
    if not isinstance(wl, list):
        wl = []
    cfg["watchlist"] = [str(s).strip().upper() for s in wl if isinstance(s, str) and s.strip()][:60]

    ui = _block(cfg, "ui")
    ui["banner_dismissed_alpaca"] = bool(ui.get("banner_dismissed_alpaca", False))
    # Appearance: an unknown value paints the default rather than a broken shell (theme.js clamps too,
    # so the file and the page agree about what is legal).
    ui["theme"] = ui.get("theme") if ui.get("theme") in ("dark", "light", "contrast") else "dark"
    ui["accent"] = ui.get("accent") if ui.get("accent") in (
        "cobalt", "teal", "green", "lime", "amber", "orange", "magenta", "violet") else "cobalt"
    ui["density"] = ui.get("density") if ui.get("density") in (
        "comfortable", "compact", "dense") else "comfortable"
    try:
        ui["wizard_resume_step"] = max(0, int(ui.get("wizard_resume_step", 0)))
    except (TypeError, ValueError):
        ui["wizard_resume_step"] = 0

    alp = _block(cfg, "alpaca")
    feed = str(alp.get("feed", "iex") or "iex").lower()
    alp["feed"] = feed if feed in ("iex", "sip", "delayed_sip") else "iex"
    try:
        alp["snapshot_seconds"] = min(max(float(alp.get("snapshot_seconds", 5.0)), 1.0), 60.0)
    except (TypeError, ValueError):
        alp["snapshot_seconds"] = 5.0
    alp["enabled"] = bool(alp.get("enabled", False))
    alp["paper"] = bool(alp.get("paper", True))
    alp["key_id"] = str(alp.get("key_id", "") or "").strip()
    alp["secret"] = str(alp.get("secret", "") or "").strip()
    syms = alp.get("view_symbols", []) or []
    if not isinstance(syms, list):
        syms = []
    alp["view_symbols"] = [s.strip().upper() for s in syms if isinstance(s, str) and s.strip()][:30]
    return cfg


def enabled_symbols(cfg: dict[str, Any]) -> list[str]:
    return [i["symbol"] for i in cfg.get("instruments", []) if i.get("enabled")]


def instrument_cfg(cfg: dict[str, Any], symbol: str) -> dict | None:
    for inst in cfg.get("instruments", []):
        if inst.get("symbol") == symbol:
            return inst
    return None
