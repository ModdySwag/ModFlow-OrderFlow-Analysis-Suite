"""Third-party platform integrations — setup workflow, account links, plans, local detection, bridges.

Two platforms live here, both optional, both free-first:

  * **Sierra Chart** — read over its own DTC protocol server. The suite is the client; the server is
    theirs; nothing is installed into their software.
  * **Bookmap** — read over a small add-on that republishes Bookmap's own trade/depth stream on
    loopback (`data/bookmap_addon/`, read by `data/bookmap_client.py`). Bookmap publishes no
    market-data-out API and no local server, so this is the only honest direction: *their* add-on API
    inside *their* process, our reader on the other end of a loopback socket.

What matters for honesty in both halves:

  * the free path is real and needs no payment — a Sierra trial with delayed data, or Bookmap Digital
    with an account (crypto, one instrument at a time);
  * paid tiers are listed with their published prices **and the date they were read**, with a link to
    the source, and the pages say plainly what is charged separately (exchange/data fees);
  * limitations are stated where they bite (Bookmap's symbol caps, its shorter free backfill, the
    licence gate on its API-plugins dialog) rather than discovered later;
  * only the vendor's own https pages open from the UI (plus the one Bookmap GitHub org the API
    template comes from) — `validate_url` is the allow-list, and nothing bypasses it.
"""

from __future__ import annotations

import os
import re
import sys
import webbrowser
import zipfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

# ══════════════════════════════════════════════════════════════════════════════════════════════
# Sierra Chart
# Read from the vendor's own pricing page; keep this date current when the prices are re-read.
# ══════════════════════════════════════════════════════════════════════════════════════════════
PRICES_AS_OF = "8 September 2026"
VENDOR_HOST = "sierrachart.com"
VENDOR_HOME = "https://www.sierrachart.com/"

LINKS = [
    {"id": "download", "label": "Download the platform", "url": VENDOR_HOME + "index.php?page=doc/SoftwareDownload.php",
     "why": "the installer; the software itself is free to install and run"},
    {"id": "trial", "label": "What the free trial includes", "url": VENDOR_HOME + "index.php?page=doc/helpdetails59.php",
     "why": "start here — this is the no-payment path"},
    {"id": "delayed", "label": "Delayed streaming exchange data (free)", "url": VENDOR_HOME + "index.php?page=doc/DelayedExchangeDataFeed.php",
     "why": "delayed data needs no service package and no exchange fee"},
    {"id": "create", "label": "Create an account", "url": VENDOR_HOME + "RegisterStep1.php",
     "why": "needed even for the free trial: it is the login the software uses"},
    {"id": "control", "label": "Account control panel (login)", "url": VENDOR_HOME + "UserControlPanel.php",
     "why": "where you activate a package, add credit and see what is running"},
    {"id": "activate", "label": "Activate / change a service package", "url": VENDOR_HOME + "UserControlPanel.php?page=ServicesActivation",
     "why": "switch between free, Package 3/5, or an integrated package at any time"},
    {"id": "pricing", "label": "Plans and pricing (all packages)", "url": VENDOR_HOME + "index.php?page=doc/Packages.php",
     "why": f"the source of the figures below, read {PRICES_AS_OF}"},
    {"id": "payment", "label": "Add credit / make a payment", "url": VENDOR_HOME + "UserControlPanel.php?page=AddAccountCredit",
     "why": "paid packages are billed against account credit"},
    {"id": "dtc", "label": "DTC protocol (what this bridge speaks)", "url": VENDOR_HOME + "index.php?page=doc/DTCProtocol.php",
     "why": "an open, public-domain interface — no plugin of theirs is installed in this suite"},
    {"id": "setup", "label": "Setup instructions", "url": VENDOR_HOME + "index.php?page=doc/setup.php",
     "why": "their own walk-through if you want it beside ours"},
    {"id": "support", "label": "Support board", "url": VENDOR_HOME + "SupportBoard.php",
     "why": "for account and data questions this suite cannot answer"},
    {"id": "futures", "label": "Understanding real-time futures data", "url": VENDOR_HOME + "index.php?page=doc/FuturesData.php",
     "why": "why exchange fees exist, in their words"},
]

# Free first, then the published paid tiers. `kind` drives the suite's behaviour (see `workflow`).
PLANS = [
    {"id": "free", "name": "Free (trial + delayed data)", "price": "0", "period": "no payment",
     "kind": "free", "highlight": True,
     "includes": ["the full charting and analysis software", "the free trial period on the highest package",
                  "delayed streaming exchange data, no service package required",
                  "simulated trading service", "the DTC server this suite reads"]},
    {"id": "p3", "name": "Service Package 3 — Base Standard", "price": "26", "period": "USD/month",
     "kind": "base", "includes": ["all software functionality except the advanced set",
                                  "Sierra-provided data and simulated trading",
                                  "no connection to external data/trading services"]},
    {"id": "p5", "name": "Service Package 5 — Base + Advanced Features", "price": "36", "period": "USD/month",
     "kind": "base", "includes": ["adds the advanced feature set", "still Sierra-provided data only"]},
    {"id": "p10", "name": "Service Package 10 — Integrated Standard", "price": "36", "period": "USD/month",
     "kind": "integrated", "includes": ["required to connect external data or trading services",
                                        "required for the Denali exchange data feed"]},
    {"id": "p11", "name": "Service Package 11 — Integrated + Advanced", "price": "46", "period": "USD/month",
     "kind": "integrated", "includes": ["integrated connectivity plus the advanced feature set"]},
    {"id": "p12", "name": "Service Package 12 — Integrated + Advanced + Market by Order", "price": "56",
     "period": "USD/month", "kind": "integrated",
     "includes": ["adds market-by-order data", "deepest order-book detail of the tiers"]},
]

PLAN_IDS = [plan["id"] for plan in PLANS]
CAVEATS = [
    "Exchange data fees are charged separately by the exchanges, on top of any service package. The "
    "free and delayed paths avoid them.",
    "Multi-month purchases carry a discount on their side; there is no one-time purchase option.",
    "Prices above are quoted from the vendor's pricing page read " + PRICES_AS_OF + " — always check "
    "the linked page before paying.",
]

# ══════════════════════════════════════════════════════════════════════════════════════════════
# Bookmap
# Read from bookmap.com/packages-comparison + their knowledge base on this date. Bookmap sells
# SOFTWARE tiers; market data is a separate purchase on every tier that needs it (crypto is free).
# ══════════════════════════════════════════════════════════════════════════════════════════════
BOOKMAP_PRICES_AS_OF = "15 September 2026"
BOOKMAP_HOST = "bookmap.com"
BOOKMAP_HOME = "https://bookmap.com/"
#: The one non-vendor host allowed: Bookmap's own API organisation on GitHub (the add-on references).
BOOKMAP_CODE_HOST = "github.com"
BOOKMAP_CODE_PREFIX = "/BookmapAPI/"

BOOKMAP_LINKS = [
    {"id": "download", "label": "Get Bookmap", "url": BOOKMAP_HOME,
     "why": "the platform itself; installing it is free — the licence decides what it can show"},
    {"id": "create", "label": "Create an account", "url": BOOKMAP_HOME + "portal/",
     "why": "needed even for the free tier: it is the login the software and the portal use"},
    {"id": "portal", "label": "Account portal (licence, data, invoices)", "url": BOOKMAP_HOME + "portal/",
     "why": "where the plan, data add-ons and connections are managed"},
    {"id": "pricing", "label": "Plans and pricing (all packages)", "url": BOOKMAP_HOME + "packages-comparison/",
     "why": f"the source of the figures below, read {BOOKMAP_PRICES_AS_OF}"},
    {"id": "free", "label": "What each tier includes, in their words", "url": BOOKMAP_HOME + "knowledgebase/docs/KB-IntroductionToBookmap-Connectivity",
     "why": "the free tier's own limits: crypto only, one instrument at a time, its backfill window"},
    {"id": "crypto", "label": "Crypto connectivity (the free path)", "url": BOOKMAP_HOME + "crypto/",
     "why": "which exchanges the free crypto connections cover"},
    {"id": "datapricing", "label": "BookmapData for futures (what data costs)", "url": BOOKMAP_HOME + "bmdata",
     "why": "market data is NOT in the subscription price — this is the separate bill"},
    {"id": "dxfeed", "label": "dxFeed for stocks and futures", "url": BOOKMAP_HOME + "dxfeed",
     "why": "the full-depth US equities route, and the futures-per-exchange pricing"},
    {"id": "addons", "label": "Add-ons and which tier unlocks them", "url": BOOKMAP_HOME + "addons-info/",
     "why": "why the advanced add-ons are sold with Global Plus"},
    {"id": "setup_api", "label": "The add-on API tutorial (what this bridge is built against)",
     "url": BOOKMAP_HOME + "knowledgebase/docs/API-Tutorial",
     "why": "their own guide: jars from the install's lib folder, install via Configure API plugins"},
    {"id": "python_api", "label": "Bookmap's Python add-on API (GitHub)",
     "url": "https://github.com/BookmapAPI/python-api",
     "why": "the other way to write an add-on: Python inside Bookmap, MIT-licensed"},
    {"id": "releases", "label": "Release notes (API-plugin changes)", "url": BOOKMAP_HOME + "knowledgebase/docs/KB-ReleaseNotes",
     "why": "their log of API and plugin-gate changes — worth a look after a Bookmap update"},
    {"id": "support", "label": "Knowledge base", "url": BOOKMAP_HOME + "knowledgebase/",
     "why": "for licence and data questions this suite cannot answer"},
]

#: Free first. `instruments` is the tier's own published cap and `backfill` its own published window —
#: both are quoted rather than implied, because they are exactly what limits a widget board.
BOOKMAP_PLANS = [
    {"id": "digital", "name": "Bookmap Digital — free", "price": "0", "period": "no payment",
     "kind": "free", "highlight": True, "instruments": 1, "backfill": "1 hour (crypto)",
     "includes": ["crypto market depth from Binance, Bitfinex and 20+ exchanges",
                  "one instrument at a time", "1 hour of crypto backfill",
                  "the same chart engine as the paid tiers",
                  "an account is required, payment is not"]},
    {"id": "digitalplus", "name": "Bookmap Digital+", "price": "19", "period": "USD/month",
     "yearly": "16", "kind": "base", "instruments": 3, "backfill": "3 hours (crypto)",
     "includes": ["3 instruments at a time", "3 hours of crypto backfill",
                  "VWAP and the Correlation Tracker", "still crypto-only"]},
    {"id": "global", "name": "Bookmap Global", "price": "49", "period": "USD/month",
     "yearly": "39", "lifetime": "990", "kind": "integrated", "instruments": 10,
     "backfill": "24 hours (crypto) · market-data dependent",
     "includes": ["stocks, futures and crypto", "10 instruments at a time",
                  "record & replay, multiple broker support", "cross-trading between instruments",
                  "2nd free licence for replay"]},
    {"id": "globalplus", "name": "Bookmap Global Plus", "price": "99", "period": "USD/month",
     "yearly": "79", "lifetime": "1990", "kind": "integrated", "instruments": 20,
     "backfill": "7 days (crypto) · market-data dependent",
     "includes": ["20 instruments at a time", "the advanced add-ons (Liquidity, Absorption, Market Pulse…)",
                  "trade directly from the chart", "weekly live trading sessions"]},
]

BOOKMAP_PLAN_IDS = [plan["id"] for plan in BOOKMAP_PLANS]
BOOKMAP_CAVEATS = [
    "Bookmap sells software tiers only: **market data is not included** on any of them. Crypto "
    "connections are free; futures/stock depth is separate (BookmapData $34–79/mo per exchange or "
    "bundle, dxFeed futures $37/mo per exchange, US equities $34–119/mo, Rithmic $40–101/mo).",
    "The free Digital tier is crypto-only and shows **one instrument at a time**, with the shortest "
    "backfill (1 hour). It is enough to run and verify this bridge; it is not enough to fill a widget "
    "board with US futures.",
    "Bookmap's **API-plugins dialog can be licence-gated**: the Add button is locked on some "
    "subscriptions, and the marketplace's advanced add-ons ship with Global Plus. This suite's bridge "
    "is a plain API plugin — if the dialog refuses it, no add-on integration is possible on that "
    "licence, and the suite says so instead of pretending.",
    "There is no market-data-out API and no local server in Bookmap: the only way out is an add-on "
    "running inside it. That is why this integration ships a small add-on for you to build and add "
    "once (it is read-only and loopback-only).",
    "Prices above are quoted from the vendor's comparison page read " + BOOKMAP_PRICES_AS_OF +
    " (monthly; yearly billing is cheaper per month, and Global/Global+ offer lifetime licences). "
    "Always check the linked page before paying.",
]


def _plan(plan_id: str) -> dict[str, Any]:
    for plan in PLANS:
        if plan["id"] == plan_id:
            return plan
    return PLANS[0]


def _bookmap_plan(plan_id: str) -> dict[str, Any]:
    for plan in BOOKMAP_PLANS:
        if plan["id"] == plan_id:
            return plan
    return BOOKMAP_PLANS[0]


def workflow(plan_id: str = "free") -> dict[str, Any]:
    """The setup steps for this plan, and what the SUITE changes when it is selected."""
    plan = _plan(plan_id)
    paid = plan["kind"] != "free"
    steps = [
        {"n": 1, "title": "Install the platform",
         "text": "Download and install it with the link below. Installing is free; nothing is paid at "
                 "this step.",
         "link": "download"},
        {"n": 2, "title": "Create the account you will log in with",
         "text": "Even the free trial needs an account: it is the login the software asks for on "
                 "first start. Use the same email you will keep.",
         "link": "create"},
        {"n": 3, "title": "Start on the free path",
         "text": "Keep the free trial running and add the delayed streaming exchange data feed. "
                 "No service package and no exchange fee is needed to see data and to feed this suite.",
         "link": "delayed" if not paid else "activate"},
        {"n": 4, "title": "Turn on the DTC protocol server",
         "text": "In the platform: Global Settings → Server Settings → DTC Protocol Server. Enable it, "
                 "set the encoding to JSON, and note the host and port (11099 by default).",
         "link": "dtc"},
        {"n": 5, "title": "Point this suite at it",
         "text": "Fill the connection card below with the same host, port and — if you set them there — "
                 "credentials, then press Test connection.",
         "link": ""},
        {"n": 6, "title": "Load it into your workflow",
         "text": "Switch the integration toggle on and pick the plan you are actually running. The suite "
                 "then labels the feed, keeps the bridge in its status bar, and stops asking questions "
                 "you have already answered.",
         "link": ""},
    ]
    if paid:
        steps.insert(3, {"n": 4, "title": "Activate the package you chose",
                         "text": f"{plan['name']} at {plan['price']} {plan['period']}: activate it in "
                                 "the control panel and add account credit. Exchange fees are separate.",
                         "link": "activate"})
        for i, step in enumerate(steps):
            step["n"] = i + 1
    return {
        "plan": plan["id"],
        "plan_kind": plan["kind"],
        "steps": steps,
        "suite_changes": [
            f"Status bar shows “Sierra: {plan['id']}” with the bridge state.",
            "Data-quality label follows the plan: "
            + ("delayed data — timestamps are honest about the delay" if not paid
               else "real-time data — exchange fees already apply"),
            "The bridge stays optional: the built-in free feeds keep running either way.",
            *(["A banner reminds you that external feeds need an integrated package (10/11/12)."]
              if plan["kind"] == "base" else []),
        ],
    }


def bookmap_workflow(plan_id: str = "digital") -> dict[str, Any]:
    """The setup steps for a Bookmap tier, free path first, and what the SUITE changes with it."""
    plan = _bookmap_plan(plan_id)
    paid = plan["kind"] != "free"
    steps = [
        {"n": 1, "title": "Install Bookmap",
         "text": "Installing the platform is free. What the licence unlocks is what the licence "
                 "unlocks — the free tier below is real, and it is crypto.",
         "link": "download"},
        {"n": 2, "title": "Create the account first",
         "text": "The account is the login the software uses, and the portal is where the licence and "
                 "any data subscription live. Nothing is paid at this step.",
         "link": "create"},
        {"n": 3, "title": "Start on the free path — Bookmap Digital",
         "text": "Crypto market depth, one instrument at a time, 1 hour of backfill, no payment. Point "
                 "Bookmap at a crypto connection (Binance/Bitfinex and 20+ others are included) and let "
                 "a chart stream — that is what the bridge republishes.",
         "link": "free"},
        {"n": 4, "title": "Add the bridge add-on (once)",
         "text": "Bookmap has no data-out API, so this suite ships a small read-only add-on with the "
                 "app — no compiler needed. In Bookmap open Settings → Configure API plugins → Add and "
                 "pick the ofap-bridge.jar from the folder shown on this card (its source and its "
                 "README travel beside it). It binds 127.0.0.1 only and never trades.",
         "link": "setup_api"},
        {"n": 5, "title": "Point this suite at it",
         "text": "The add-on prints the port it bound (8791 by default) in Bookmap's log. Fill the "
                 "bridge card below with the same host and port, then press Test connection.",
         "link": ""},
        {"n": 6, "title": "Load it into your workflow",
         "text": "Switch the toggle on and pick the tier you actually run. The suite then labels the "
                 "feed, keeps the bridge state in its status bar, and stops asking questions you have "
                 "already answered.",
         "link": ""},
        {"n": 7, "title": "If Add is locked in Bookmap",
         "text": "Bookmap licence-gates the API-plugins dialog on some subscriptions. If it refuses "
                 "the jar, that is their rule for your tier — leave this integration off and the suite "
                 "keeps running on its own free feeds.",
         "link": "addons"},
    ]
    if paid:
        steps.insert(3, {"n": 4, "title": "Activate the tier you chose",
                         "text": f"{plan['name']} at {plan['price']} {plan['period']}"
                                 + (f" ({plan['yearly']}/month billed yearly" +
                                    (f", or {plan['lifetime']} lifetime" if plan.get("lifetime") else "")
                                    + ")" if plan.get("yearly") else "")
                                 + ": activate it in the portal. Any real-time stock/futures data is a "
                                   "separate subscription — market data is not in the tier price.",
                         "link": "pricing"})
        for i, step in enumerate(steps):
            step["n"] = i + 1
    return {
        "plan": plan["id"],
        "plan_kind": plan["kind"],
        "instruments": plan["instruments"],
        "backfill": plan["backfill"],
        "steps": steps,
        "suite_changes": [
            f"Status bar shows “Bookmap: {plan['id']}” with the bridge state.",
            "Data-quality label follows the tier: "
            + ("crypto depth, one instrument at a time — the add-on republishes what the chart streams"
               if not paid else f"the licence's own depth, up to {plan['instruments']} instruments"),
            "The bridge is read-only and loopback-only: no orders, no account details, nothing stored "
            "from Bookmap beyond host/port/tier.",
            "The bridge stays optional: the built-in free feeds keep running either way.",
            "If Bookmap's API-plugins dialog is locked on your licence, this integration cannot be "
            "installed — the suite says that rather than half-working.",
        ],
    }


def catalogue() -> dict[str, Any]:
    """Everything the view needs, free path first. Sierra stays first: existing callers index [0]."""
    return {
        "platforms": [{
            "id": "sierra",
            "name": "Sierra Chart",
            "vendor_url": VENDOR_HOME,
            "why": "an optional second data source and execution platform; this suite reads it over DTC "
                   "without installing anything into it",
            "free_tier": True,
            "bridge": "dtc",
            "bridge_where": "in their software (Global Settings → Server Settings → DTC Protocol Server)",
            "links": LINKS,
            "plans": PLANS,
            "prices_as_of": PRICES_AS_OF,
            "caveats": CAVEATS,
        }, {
            "id": "bookmap",
            "name": "Bookmap",
            "vendor_url": BOOKMAP_HOME,
            "why": "an optional heatmap/order-flow view of its own; this suite reads its live trades and "
                   "depth through a small read-only add-on the suite ships",
            "free_tier": True,
            "bridge": "bookmap-addon",
            "bridge_where": "in their software (Settings → Configure API plugins → Add)",
            "links": BOOKMAP_LINKS,
            "plans": BOOKMAP_PLANS,
            "prices_as_of": BOOKMAP_PRICES_AS_OF,
            "caveats": BOOKMAP_CAVEATS,
            "limits": {
                "free": {"instruments": 1, "backfill": "1 hour (crypto)", "markets": "crypto only"},
                "addon_gate": "the API-plugins dialog can be licence-locked; the marketplace's advanced "
                              "add-ons ship with Global Plus",
                "data": "market data is billed separately on every tier (crypto connections are free)",
            },
        }],
    }


# ── local install detection (paths, a manifest and a folder listing only) ───────────────────
SIERRA_CANDIDATES = (r"C:\SierraChart", r"C:\Program Files\Sierra Chart",
                     r"C:\Program Files (x86)\SierraChart")
BOOKMAP_CANDIDATES = (r"C:\Program Files\Bookmap", r"C:\Program Files (x86)\Bookmap")


def _sierra_version(root: Path) -> str:
    """The platform writes its build number to a plain text file; nothing else is touched."""
    for name in ("VersionNumber.txt", "version.txt"):
        try:
            text = (root / name).read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if text and len(text) < 40:
            return text.splitlines()[0].strip()
    return ""


def _bookmap_version(root: Path) -> str:
    """Bookmap stamps its build into `Bookmap.jar`'s manifest (`BookMap-version: 7.8.0 build:13`).

    Reading a manifest out of a jar is a read of the install, not of the user: no licence, account or
    config file is opened, and nothing is extracted to disk.
    """
    jar = root / "Bookmap.jar"
    if not jar.is_file():
        return ""
    try:
        with zipfile.ZipFile(jar) as bundle:
            manifest = bundle.read("META-INF/MANIFEST.MF").decode("utf-8", "replace")
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""
    match = re.search(r"^BookMap-version:\s*(.+)$", manifest, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _bookmap_api_modules() -> dict[str, Any]:
    """What the API folders hold — module names and versions only, never their contents.

    Bookmap keeps installed add-ons in `%LOCALAPPDATA%\\Bookmap\\API\\Layer0ApiModules` (data
    adapters) and `…\\Layer1ApiModules` (add-ons). The filenames carry
    `bmMin---bmMax---apiVersion---name---version`, which is enough to say whether OUR bridge is
    installed and whether the dialog has ever been used.
    """
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Bookmap" / "API"
    out: dict[str, Any] = {"dir": str(base), "present": base.is_dir(), "layer0": [], "layer1": [],
                           "bridge_installed": False}
    if not base.is_dir():
        return out
    for layer, key in (("Layer0ApiModules", "layer0"), ("Layer1ApiModules", "layer1")):
        folder = base / layer
        if not folder.is_dir():
            continue
        for jar in sorted(folder.glob("*.jar")):
            parts = jar.stem.split("---")
            name = parts[3] if len(parts) >= 5 else jar.stem
            version = parts[4] if len(parts) >= 5 else ""
            out[key].append({"name": name, "version": version})
            if "ofap" in name.lower() or "ofap" in jar.stem.lower():
                out["bridge_installed"] = True
    return out


def detect_installs() -> dict[str, Any]:
    """Where each platform is installed on this machine, if it is. Shallow on purpose: it checks for
    the executable, reads a build number, and lists API module filenames. Account files, licence keys,
    user config and logs are never opened."""
    out: dict[str, Any] = {"sierra": {"found": False}, "bookmap": {"found": False}}
    for candidate in SIERRA_CANDIDATES:
        root = Path(candidate)
        if (root / "SierraChart.exe").is_file() or (root / "SierraChart_64.exe").is_file():
            out["sierra"] = {"found": True, "path": str(root), "version": _sierra_version(root),
                             "dtc_folder": (root / "DTC").is_dir()}
            break
    for candidate in BOOKMAP_CANDIDATES:
        root = Path(candidate)
        if (root / "Bookmap.exe").is_file():
            modules = _bookmap_api_modules()
            out["bookmap"] = {"found": True, "path": str(root), "version": _bookmap_version(root),
                              "runtime": _bookmap_runtime(root),
                              "api_jars": all((root / "lib" / jar).is_file() for jar in
                                              ("bm-l1api.jar", "bm-simplified-api-wrapper.jar")),
                              "api_modules": modules,
                              "addon_folder": str((root / "lib"))}
            break
    else:
        out["bookmap"]["api_modules"] = _bookmap_api_modules()
    return out


def dtc_defaults() -> dict[str, Any]:
    """The DTC connection block's shape and defaults (11099 is the common default; match whatever the
    server dialog on your own platform shows)."""
    return {"enabled": False, "host": "127.0.0.1", "port": 11099,
            "username": "", "password": "", "use_tls": False, "symbol": "",
            "plan": "free", "integrated": False}


def bookmap_defaults() -> dict[str, Any]:
    """The Bookmap bridge block: where the add-on listens and which tier is being run.

    8791 is this suite's convention (the add-on template binds it and prints the real port to Bookmap's
    log). No credentials exist here at all — the add-on has nothing to authenticate: it is loopback
    only, and the suite never talks to Bookmap's servers.
    """
    return {"enabled": False, "host": "127.0.0.1", "port": 8791,
            "protocol": "bookmap-addon-jsonl", "symbol": "",
            "plan": "digital", "integrated": False, "addon_built": False}


def suggested_symbols(symbols: Optional[list[str]] = None) -> list[str]:
    """Symbols to offer for the probes — the user's own instruments, if any."""
    picks = [s for s in (symbols or []) if s][:8]
    return picks or ["ESZ6", "NQZ6", "BTCUSDT"]


# ── the bridge jar that ships WITH this app ─────────────────────────────────────────────────
# The add-on is built once, here, and travels inside the install: a fresh user needs no JDK and no
# compiler, only Bookmap's own four clicks. The source stays beside it for rebuilds against a
# different Bookmap generation, and the two facts that matter are compared for the user rather than
# left to fail silently: what Java the jar was built for, and what runtime their Bookmap ships.
BOOKMAP_JAR_NAME = "ofap-bridge.jar"
BOOKMAP_ADDON_DIR = Path(__file__).resolve().parents[1] / "data" / "bookmap_addon"
#: Class-file major version → the Java release. Only the mappings a JVM spec has actually defined.
JAVA_CLASS_VERSIONS = {45: "1.1", 46: "2", 47: "3", 48: "4", 49: "5", 50: "6", 51: "7", 52: "8",
                       53: "9", 54: "10", 55: "11", 56: "12", 57: "13", 58: "14", 59: "15",
                       60: "16", 61: "17", 62: "18", 63: "19", 64: "20", 65: "21", 66: "22",
                       67: "23", 68: "24", 69: "25"}


def jar_target_java(jar: Path) -> str:
    """The Java release a jar's classes need, read from the first class file's major version.

    Just the class-file header (magic, minor, major) — nothing is extracted and nothing is executed.
    """
    try:
        with zipfile.ZipFile(jar) as bundle:
            entry = next((name for name in bundle.namelist() if name.endswith(".class")), "")
            if not entry:
                return ""
            head = bundle.read(entry)[:8]
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""
    if len(head) < 8 or head[:4] != b"\xca\xfe\xba\xbe":
        return ""
    major = int.from_bytes(head[6:8], "big")
    return JAVA_CLASS_VERSIONS.get(major, str(major))


def _bookmap_runtime(root: Path) -> str:
    """The Java runtime Bookmap ships with itself (`jre/release` → JAVA_VERSION)."""
    try:
        text = (root / "jre" / "release").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    match = re.search(r'^JAVA_VERSION="([^"]+)"', text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def bridge_jar() -> dict[str, Any]:
    """Where the shipped add-on jar is, what it was built for, and the source beside it."""
    jar = BOOKMAP_ADDON_DIR / BOOKMAP_JAR_NAME
    info: dict[str, Any] = {"path": str(jar), "folder": str(BOOKMAP_ADDON_DIR),
                            "source": str(BOOKMAP_ADDON_DIR / "src"), "name": BOOKMAP_JAR_NAME,
                            "exists": jar.is_file(), "size": 0, "built_for": "", "shipped": True}
    if info["exists"]:
        try:
            info["size"] = jar.stat().st_size
        except OSError:
            info["size"] = 0
        info["built_for"] = jar_target_java(jar)
    return info


def bookmap_bridge_state() -> dict[str, Any]:
    """Everything the card needs to tell the truth about the shipped jar: does it exist, what is it
    built for, what does the local Bookmap run, and do those two agree."""
    jar = bridge_jar()
    found = detect_installs().get("bookmap", {})
    runtime = found.get("runtime", "") if found.get("found") else ""
    major = runtime.split(".")[0] if runtime else ""
    state: dict[str, Any] = {"jar": jar, "bookmap_runtime": runtime, "ok": None, "note": ""}
    if not jar["exists"]:
        state["ok"] = False
        state["note"] = ("the add-on jar is missing from this install — rebuild it from the source "
                         "folder with a JDK (see its README).")
    elif not runtime:
        state["note"] = ("Bookmap is not installed here, so there is nothing to compare the jar "
                         "against. It was built for Java " + (jar["built_for"] or "?") + ".")
    elif not jar["built_for"]:
        state["note"] = "the jar's build target could not be read; Bookmap runs Java " + runtime + "."
    elif jar["built_for"] == major:
        state["ok"] = True
        state["note"] = (f"the jar is built for Java {jar['built_for']} and your Bookmap runs "
                         f"{runtime} — it will load as-is.")
    else:
        state["ok"] = False
        state["note"] = (f"the jar is built for Java {jar['built_for']}, but this Bookmap runs "
                         f"{runtime}. Rebuild it from the source folder against that Bookmap's own "
                         f"lib jars (its README has the one-line command) before adding it.")
    return state


def reveal_bridge_jar(folder: Optional[str] = None) -> dict[str, Any]:
    """Open the add-on folder in the file manager so the jar can be picked in Bookmap's dialog.

    Refuses anything outside this app's own add-on folder: this opens what the suite shipped, never a
    path handed to it from elsewhere.
    """
    home = BOOKMAP_ADDON_DIR.resolve()
    target = Path(folder).resolve() if folder else home
    if target != home and home not in target.parents:
        return {"ok": False, "error": f"not this app's add-on folder: {target}"}
    if not target.is_dir():
        return {"ok": False, "error": f"no such folder: {target}"}
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(target))                          # noqa: S606 - opening our own folder
        else:
            webbrowser.open(target.as_uri())
    except OSError as exc:                                      # pragma: no cover - platform specific
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "folder": str(target),
            "note": "Pick " + BOOKMAP_JAR_NAME + " in Bookmap: Settings → Configure API plugins → Add…"}


# ── link safety: only the vendors' own https pages open from the UI ─────────────────────────
ALLOWED_HOSTS = {
    VENDOR_HOST,
    BOOKMAP_HOST,
    BOOKMAP_CODE_HOST,          # one organisation only — see `_path_allowed`
}


def _host_allowed(host: str) -> bool:
    host = (host or "").lower().split(":")[0]
    return any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS)


def _path_allowed(parsed: Any) -> bool:
    """`github.com` is allowed for Bookmap's API organisation only — never as a general code host."""
    if (parsed.netloc or "").lower().split(":")[0] not in ("github.com", "www.github.com"):
        return True
    return (parsed.path or "").startswith(BOOKMAP_CODE_PREFIX)


def validate_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme != "https":
        return False, f"only https links are opened (got {parsed.scheme or 'no scheme'})"
    if not parsed.netloc or not _host_allowed(parsed.netloc):
        return False, f"host not on the allow-list: {parsed.netloc or '(none)'}"
    if not _path_allowed(parsed):
        return False, f"path not on the allow-list: {parsed.path or '(none)'}"
    return True, ""


def open_url(url: str) -> dict[str, Any]:
    """Open an allow-listed page in the default browser. Never raises."""
    ok, reason = validate_url(url)
    if not ok:
        return {"ok": False, "url": str(url), "error": reason}
    try:
        opened = bool(webbrowser.open(str(url), new=2))
    except Exception as exc:                                    # noqa: BLE001 - report, never raise
        return {"ok": False, "url": str(url), "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "url": str(url), "opened": opened,
            "note": "Opened in your default browser." if opened else
                    "The browser did not confirm; check for a new tab."}
