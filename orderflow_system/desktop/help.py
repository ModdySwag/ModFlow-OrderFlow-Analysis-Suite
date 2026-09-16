"""
Help Centre support — the facts and the system check behind the in-app help system (§79).

The Help module itself is front-end (the topic corpus, the search engine and the panel), but two
things it shows cannot be invented in the browser:

  * **the facts** — the app's name, version, licence, credits and the folders it writes to, so the
    About card and the help's footer quote the program rather than a copy of it;
  * **the system check** — the configuration errors and system irregularities the Simple interface
    warns about, each one derived from real state (the engine controller, the config file, the log
    tail, the database file) and each one pointing at the help topic that explains it.

`check_report()` is a pure function of the inputs it is handed (config, engine status, storage
numbers, log text, the MT5 bridge probe), so `test_help.py` can drive every branch without an
engine, a network or a database — and the API layer is a thin wrapper that gathers live values and
calls it.

Nothing here writes: the checks read state and name a fix. Every emitted `action` is one of
`ACTIONS`, the list the UI knows how to run; an action outside that list is a bug, not a button.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from orderflow_system import __version__
from orderflow_system.desktop import config_store

#: The display name (the repo folder, the import package and the config dir keep their older
#: spelling on purpose — renaming them would orphan the owner's settings, database and shortcuts).
APP_NAME = "ModFlow OrderFlow Analysis Suite"
APP_TAGLINE = "Order-flow analysis workstation — footprint, depth, delta and profile tooling"
APP_LICENCE = "MIT"
APP_CHANNEL = "beta"                     # the version string the artefacts carry: 0.1.0-beta

#: The one place the UI reads credits from. `made_by` and `upstream` are the LICENSE's own words;
#: the thanks list is drawn from the repository's notices (README, THIRD_PARTY_NOTICES).
CREDITS: dict[str, Any] = {
    "made_by": "Moddy",
    "made_by_url": "https://moddys.net",
    "upstream": "Mahmoud — original work",
    "upstream_url": "https://github.com/mahmoud20138/OrderFlow-Analysis-Pro",
    "methodology": "Fabio Testa's orderflow methodology",
    #: The one-liner the menu bar's About card prints (the full list above is the About page's).
    "thanks_line": "Thanks to Mahmoud (the original project), Fabio Testa (the methodology), the "
                   "public venues whose data this reads, and the open-source stack it is built on.",
    "thanks": [
        "Mahmoud, whose original OrderFlow-Analysis-Pro this distribution builds on (MIT).",
        "Fabio Testa, whose orderflow methodology the detectors, profile framing and the state "
        "machine follow.",
        "The public venues whose keyless market data this program reads: Bybit, Binance Futures, "
        "OKX and Hyperliquid.",
        "Alpaca, MetaTrader 5, Deribit, SEC EDGAR, CoinGecko and alternative.me for the optional "
        "data the harnesses reach when a user links an account.",
        "TradingView, for Lightweight Charts™ (Apache-2.0), the only vendored front-end library.",
        "The open-source stack this is built on: FastAPI, Starlette, Uvicorn, pywebview, pythonnet, "
        "websockets, aiohttp, aiosqlite and python-telegram-bot.",
    ],
}

#: External links the help system offers, with the kind the UI badges them by. Kept short on
#: purpose: every one is a place a user of this program actually needs (its own pages, the venues
#: it reads, the brokers it links) rather than a link for the sake of a link.
LINKS: list[dict[str, str]] = [
    {"label": "moddys.net", "url": "https://moddys.net", "kind": "project"},
    {"label": "Original project on GitHub (Mahmoud)", "kind": "upstream",
     "url": "https://github.com/mahmoud20138/OrderFlow-Analysis-Pro"},
    {"label": "Bybit", "url": "https://www.bybit.com", "kind": "venue"},
    {"label": "Binance Futures", "url": "https://www.binance.com/en/futures", "kind": "venue"},
    {"label": "OKX", "url": "https://www.okx.com", "kind": "venue"},
    {"label": "Hyperliquid", "url": "https://app.hyperliquid.xyz", "kind": "venue"},
    {"label": "Alpaca — API keys (paper and live)", "kind": "broker",
     "url": "https://app.alpaca.markets/paper/dashboard/overview"},
    {"label": "MetaTrader 5 download", "url": "https://www.metatrader5.com/en/download", "kind": "broker"},
    {"label": "Deribit (crypto options)", "url": "https://www.deribit.com", "kind": "venue"},
    {"label": "ntfy (phone push, no account)", "url": "https://ntfy.sh", "kind": "tool"},
    {"label": "Telegram @BotFather (create a bot)", "url": "https://t.me/BotFather", "kind": "tool"},
    {"label": "SEC EDGAR (US filings)", "url": "https://www.sec.gov/edgar/searchedgar/companysearch", "kind": "tool"},
    {"label": "CoinGecko", "url": "https://www.coingecko.com", "kind": "tool"},
    {"label": "TradingView Lightweight Charts™", "kind": "library",
     "url": "https://github.com/tradingview/lightweight-charts"},
]

#: Every in-app action a check may name. The UI maps these onto the app's own functions; a value
#: that is not here never reaches the page (the check names a topic instead).
ACTIONS: tuple[str, ...] = (
    "start-engine",
    "open-settings",
    "open-instruments",
    "open-logs",
    "open-wizard",
    "open-folder-config",
    "open-folder-logs",
    "open-folder-backup",
)

#: Levels, worst first: the Simple interface sorts by this and only draws the failed ones.
LEVELS: tuple[str, ...] = ("error", "warn", "notice", "ok")

#: A tick older than this (when the engine says it is running) means prints have stopped arriving.
TICK_QUIET_MS = 120_000
#: The database file size at which the help suggests a retention pass.
DB_LARGE_BYTES = 2 * 1024 * 1024 * 1024
#: How much of the log's tail the error check reads, and how many lines it counts before it stops.
LOG_TAIL_BYTES = 200_000
LOG_ERROR_CAP = 25


# ──────────────────────────────────────────────────────────────
# The facts (About, footer, the support block)
# ──────────────────────────────────────────────────────────────


def app_dir() -> Path:
    """The folder the program itself lives in — the repo tree, or the frozen app's directory."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def app_paths() -> dict[str, str]:
    return {
        "app": str(app_dir()),
        "config": str(config_store.config_path()),
        "config_dir": str(config_store.config_dir()),
        "log": str(config_store.log_path()),
        "db": str(config_store.db_path()),
        "exports": str(config_store.config_dir() / "exports"),
    }


def app_facts() -> dict[str, Any]:
    """Name, version and environment — everything the About card prints, and nothing secret."""
    return {
        "name": APP_NAME,
        "tagline": APP_TAGLINE,
        "version": __version__,
        "channel": APP_CHANNEL,
        "licence": APP_LICENCE,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": sys.platform,
        "frozen": bool(getattr(sys, "frozen", False)),
        "paths": app_paths(),
    }


# ──────────────────────────────────────────────────────────────
# The system check
# ──────────────────────────────────────────────────────────────


def _finding(check_id: str, level: str, title: str, detail: str, *,
             topic: str = "", view: str = "", action: str = "") -> dict[str, Any]:
    """One row of the system check.

    `level` is one of LEVELS; `topic` is a help-corpus topic id the UI can open; `view` is a panel
    to jump to; `action` is a value from ACTIONS. A caller never passes all three — the row names
    the single best next step plus the topic that explains it.
    """
    assert level in LEVELS, f"unknown check level: {level}"
    assert not action or action in ACTIONS, f"unknown help action: {action}"
    return {"id": check_id, "level": level, "title": title, "detail": detail,
            "topic": topic, "view": view, "action": action}


def _log_tail(path: Path) -> str:
    """The last slice of the log file, as text (missing file → empty string, never an error)."""
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - LOG_TAIL_BYTES))
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _loopback(host: str) -> bool:
    host = (host or "").strip().lower()
    return host in ("127.0.0.1", "localhost", "::1", "testserver") or host.startswith("127.")


def check_report(cfg: dict[str, Any] | None = None,
                 status: dict[str, Any] | None = None,
                 storage: dict[str, Any] | None = None,
                 log_text: str | None = None,
                 mt5: dict[str, Any] | None = None,
                 now_ms: int | None = None) -> dict[str, Any]:
    """The system check: configuration errors and irregularities, as data.

    Every input is injectable so the branches are testable without an engine; each defaults to the
    live value the API layer would hand it. The result is `{"checks": [...], "counts": {...},
    "ok": bool}` — sorted worst-first, so the panel and the badge do not have to re-sort anything.
    """
    from orderflow_system.desktop import engine as engine_mod

    cfg = cfg if cfg is not None else config_store.load_config()
    status = status if status is not None else engine_mod.engine.status()
    mt5 = mt5 if mt5 is not None else engine_mod.mt5_status()
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    checks: list[dict[str, Any]] = []

    # ── the engine ───────────────────────────────────────────────────────────────
    running = bool(status.get("running"))
    symbols = list(status.get("symbols") or [])
    if config_store.config_path().is_file():
        checks.append(_finding(
            "config.file", "ok", "Your settings file is being read",
            f"Everything you change in the app is written to {config_store.config_path()} — never to "
            "the program folder."))
    else:
        checks.append(_finding(
            "config.file", "notice", "No settings file yet",
            "The app is running on its shipped defaults; your first change creates the file. That "
            "is normal for a fresh install.",
            topic="data.config_file", view="settings"))
    if status.get("error"):
        checks.append(_finding(
            "engine.error", "error", "The engine stopped with an error",
            f"{status.get('error')} — the Logs view has the full trace, and the engine can be "
            "started again from the top bar.",
            topic="fix.engine_error", view="logs", action="open-logs"))
    if not bool(cfg.get("instruments")):
        checks.append(_finding(
            "config.no_instruments", "error", "The config holds no instruments at all",
            "The instruments list is empty, so nothing can stream. Restore the shipped defaults "
            "or import a venue's list again.",
            topic="fix.no_instruments", view="instruments", action="open-instruments"))
    elif not [i for i in cfg.get("instruments", []) if i.get("enabled")]:
        checks.append(_finding(
            "config.no_enabled", "error", "No instrument is enabled",
            "Every instrument is switched off, so starting the engine would stream nothing. Tick "
            "at least one in Instruments.",
            topic="fix.no_instruments", view="instruments", action="open-instruments"))
    if not running:
        checks.append(_finding(
            "engine.stopped", "notice", "The engine is stopped",
            "Panels show demo data or their last known values until the engine runs; nothing is "
            "being recorded. Start it from the top bar when you are ready to watch the market.",
            topic="start.engine", view="overview", action="start-engine"))
    else:
        checks.append(_finding(
            "engine.running", "ok", "The engine is running",
            f"{len(symbols)} instrument(s) on {status.get('source') or 'the configured source'}, "
            f"up {int(status.get('uptime_s') or 0)} s."))
        skipped = status.get("skipped") or {}
        if skipped:
            names = ", ".join(sorted(str(k) for k in skipped))[:200]
            checks.append(_finding(
                "engine.skipped", "warn", "Some instruments were skipped at start",
                f"{len(skipped)} symbol(s) could not be subscribed: {names}. The reason for each is "
                "in the log; the usual cause is a venue that does not list the symbol.",
                topic="fix.skipped_symbols", view="logs", action="open-logs"))
        per_symbol = status.get("per_symbol") or []
        newest = max([int(row.get("last_tick_ms") or 0) for row in per_symbol] or [0])
        if per_symbol and int(status.get("uptime_s") or 0) > 60 and (
                newest == 0 or now_ms - newest > TICK_QUIET_MS):
            age = "no prints yet" if newest == 0 else f"last print {int((now_ms - newest) / 1000)} s ago"
            checks.append(_finding(
                "feed.quiet", "warn", "No prints are arriving",
                f"The engine is running but {age}. The venue may be quiet, the network may be "
                "blocked, or the chosen source may not carry these symbols — the Live chips on "
                "each panel say which state they are in.",
                topic="fix.no_data", view="instruments"))

    # ── the configured data source ───────────────────────────────────────────────
    source = str(cfg.get("data_source") or "").strip().lower()
    known = ("bybit", "binance", "hyperliquid", "okx", "mt5", "both", "alpaca", "all")
    if source and source not in known:
        listed = ", ".join(known)
        checks.append(_finding(
            "source.unknown", "error", f"Unknown data source: {source}",
            f"The config names a source this build does not have. Known: {listed}. Pick one from "
            "the ☰ menu's Connections list.",
            topic="start.sources", view="settings", action="open-settings"))
    if source in ("mt5", "both") and not mt5.get("available"):
        checks.append(_finding(
            "source.mt5_unavailable", "warn", "MetaTrader 5 is selected but not usable here",
            f"{mt5.get('reason') or 'the MetaTrader5 bridge is unavailable'} — crypto symbols still "
            "stream from the exchange feed.",
            topic="connect.mt5", view="settings", action="open-settings"))
    elif source in ("mt5", "both") and mt5.get("available"):
        checks.append(_finding(
            "source.mt5_ready", "ok", "The MetaTrader 5 bridge is available",
            "The terminal must be installed and left running — the bridge talks to the running "
            "terminal, not to the broker directly."))
    if source in ("mt5", "both"):
        unmapped = [i.get("symbol") for i in cfg.get("instruments", [])
                    if i.get("enabled") and i.get("mt5_symbol") == ""]
        if unmapped:
            checks.append(_finding(
                "mt5.unmapped", "notice",
                f"{len(unmapped)} MT5 instrument(s) have no broker symbol",
                f"{', '.join(str(s) for s in unmapped[:8])} — the engine cannot subscribe an MT5 "
                "symbol without your broker's name for it.",
                topic="connect.mt5_map", view="instruments", action="open-instruments"))
    if source in ("alpaca", "all"):
        alp = cfg.get("alpaca") or {}
        if not (alp.get("enabled") and alp.get("key_id") and alp.get("secret")):
            checks.append(_finding(
                "source.alpaca_unlinked", "warn", "Alpaca is selected but no account is linked",
                "The Alpaca feed needs an API key pair (a free paper account is enough). Link it in "
                "the Alpaca view, or switch the source back to the exchange feed.",
                topic="connect.alpaca", view="alpaca"))
        else:
            checks.append(_finding(
                "source.alpaca_ready", "ok", "The Alpaca account is linked",
                "Paper keys only work against the paper host and live keys only against the live "
                "host — the Alpaca view's Validate button reports which one the pair belongs to."))

    # ── optional integrations that are configured but incomplete ─────────────────
    alp = cfg.get("alpaca") or {}
    if alp.get("enabled") and not (alp.get("key_id") and alp.get("secret")):
        checks.append(_finding(
            "alpaca.partial", "warn", "Alpaca is enabled with incomplete keys",
            "One of the two values is missing, so every Alpaca call will fail with 401. Paste the "
            "pair again (paper keys only work against the paper host).",
            topic="connect.alpaca", view="alpaca"))
    telegram = cfg.get("telegram") or {}
    notify = cfg.get("notify") or {}
    channels = [
        bool(telegram.get("enabled") and telegram.get("bot_token") and telegram.get("chat_id")),
        bool((notify.get("ntfy") or {}).get("topic")),
        bool((notify.get("email") or {}).get("host") and (notify.get("email") or {}).get("to")),
        bool((cfg.get("atlas") or {}).get("webhook_url")),
    ]
    if not any(channels):
        checks.append(_finding(
            "alerts.no_channel", "notice", "No alert channel is configured",
            "Detections still appear on screen and in the Alerts view, but nothing reaches your "
            "phone or inbox. Telegram and ntfy are both free and take about two minutes.",
            topic="connect.channels", view="alerts"))

    # ── storage ──────────────────────────────────────────────────────────────────
    storage = storage or {}
    db_bytes = int(storage.get("bytes") or 0)
    if db_bytes >= DB_LARGE_BYTES:
        checks.append(_finding(
            "storage.large", "notice",
            f"The tick database is {db_bytes / 1024 ** 3:.1f} GB",
            "Retention prunes it automatically while the engine runs. A shorter window keeps it "
            "smaller; the Storage panel shows the row counts and the last pass.",
            topic="data.storage", view="settings", action="open-settings"))
    data_cfg = cfg.get("data") or {}
    if int(data_cfg.get("retention_days") or 0) == 0:
        checks.append(_finding(
            "storage.retention_off", "notice", "Tick retention is switched off",
            "With retention at 0 the database keeps every tick forever and grows without bound. "
            "Set a window (7 days is the default) unless you mean to keep everything.",
            topic="data.storage", view="settings", action="open-settings"))

    # ── the log ──────────────────────────────────────────────────────────────────
    text = log_text if log_text is not None else _log_tail(config_store.log_path())
    if text:
        lines = [ln for ln in text.splitlines()
                 if (" ERROR " in f" {ln} " or " CRITICAL " in f" {ln} ")]
        if lines:
            checks.append(_finding(
                "log.errors", "warn", f"The log holds {len(lines)} error line(s)",
                f"Most recent: {lines[-1].strip()[:220]} — the Logs view filters by level, and "
                "'Copy diagnostics' (Tools menu) gathers what a bug report needs.",
                topic="support.report", view="logs", action="open-logs"))

    # ── how the app is exposed ───────────────────────────────────────────────────
    host = str((cfg.get("dashboard") or {}).get("host") or "127.0.0.1")
    if not _loopback(host):
        checks.append(_finding(
            "security.lan", "warn", f"The control API is served beyond this machine ({host})",
            "Anything on the network that can reach this port sees the UI (and the read endpoints). "
            "That is a deliberate choice in the config — set dashboard.host back to 127.0.0.1 to "
            "keep it local.",
            topic="data.security", view="settings", action="open-settings"))
    else:
        checks.append(_finding(
            "security.local", "ok", "The app answers this machine only",
            f"The UI and the control API are bound to {host or '127.0.0.1'} — another machine on "
            "your network cannot reach them, and market data is pulled from the public venues "
            "without an account."))

    order = {level: idx for idx, level in enumerate(LEVELS)}
    checks.sort(key=lambda c: (order.get(c["level"], 9), c["id"]))
    counts = {level: sum(1 for c in checks if c["level"] == level) for level in LEVELS}
    counts["total"] = len(checks)
    return {"checks": checks, "counts": counts,
            "ok": counts["error"] == 0 and counts["warn"] == 0}


def _config_or_none() -> tuple[dict[str, Any], str]:
    """Load the config, reporting an unreadable file instead of raising at a help panel."""
    try:
        return config_store.load_config(), ""
    except Exception as exc:                      # a hand-edited file can break json entirely
        return config_store.default_config(), f"{type(exc).__name__}: {exc}"


def report() -> dict[str, Any]:
    """Everything the help module needs from Python: facts, credits, links and the system check."""
    cfg, error = _config_or_none()
    status: dict[str, Any] = {}
    mt5: dict[str, Any] = {}
    try:
        from orderflow_system.desktop import engine as engine_mod
        status = engine_mod.engine.status()
        mt5 = engine_mod.mt5_status()
    except Exception:                             # pragma: no cover — help must never 500
        pass
    storage: dict[str, Any] = {}
    try:
        from orderflow_system.desktop import api as api_mod
        cached = api_mod._storage_cache.get("data")     # the 30 s cache the Storage panel fills
        if isinstance(cached, dict):
            storage = cached
        else:
            db = config_store.db_path()
            storage = {"bytes": db.stat().st_size if db.exists() else 0}
    except Exception:                             # pragma: no cover
        pass

    check = check_report(cfg=cfg, status=status, storage=storage, mt5=mt5)
    if error:
        check["checks"].insert(0, _finding(
            "config.unreadable", "error", "The config file could not be read",
            f"{error} — the app is running on defaults and nothing will be saved until the file is "
            "repaired or reset. 'Reset to defaults' lives in Settings ▸ config.",
            topic="data.config_file", view="settings", action="open-settings"))
        check["counts"]["error"] = check["counts"].get("error", 0) + 1
        check["counts"]["total"] = check["counts"].get("total", 0) + 1
        check["ok"] = False
    return {
        "ok": True,
        "app": app_facts(),
        "credits": CREDITS,
        "links": LINKS,
        "check": check,
        "prefs": dict((cfg.get("help") or {})),
        "generated_ms": int(time.time() * 1000),
    }
