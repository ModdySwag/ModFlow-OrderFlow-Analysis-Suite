#!/usr/bin/env python3
"""End-of-build audit: do the UI's API calls and element references resolve?

Checks, in order:
  1. every JS `api('/api/...')` path has a matching FastAPI route
  2. every `getElementById` / `$('#id')` the atlas/guide modules use exists in
     index.html or is created by one of the module templates
  3. index.html has no duplicate element ids
  4. modules import cleanly and the route tables are non-empty

Run:  .venv/Scripts/python.exe scripts/audit_ui_refs.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "orderflow_system" / "desktop" / "ui"
#: Every module that calls the API or owns element ids. The original four were the
#: only files the audit knew; the palette, scanner and Alpaca modules call just as
#: many endpoints, and a typo there is the same silent breakage.
JS_FILES = ["ui.js", "atlas.js", "atlas-v2.js", "guide.js",
            "search.js", "search-ops.js", "scanner.js", "alpaca.js", "alpaca-card.js",
            "context.js", "intent.js", "vwap.js", "market-pressure.js", "steady.js",
            "platforms.js", "study-api.js", "studies.js",
            "ofx.js", "ofx-view.js", "pause.js", "menu.js", "menubar.js", "drawings.js", "shell.js",
            "links.js", "bus.js", "watchlist.js", "news.js", "options.js", "fundamentals.js",
            "theme.js", "cursor-link.js", "strips.js", "alert-format.js", "expression.js",
            "keys.js", "freshness.js", "help.js", "help-data.js", "help-search.js", "instrument.js",
            "hint.js", "systems.js", "ramp.js", "paper.js", "ladder.js", "navreturn.js", "heatview.js",
            "presets.js", "tips.js", "feedkeys.js",
            # §147 (upgrade package): the new panels, the condition builder, the companion page and
            # the explainability layer — they call the API and own element ids like every module above.
            "orderflow.js", "alert-builder.js", "depth-history.js", "data-quality.js",
            "sessions.js", "derivatives.js", "synthetic.js", "monitor.js", "why.js"]


def routes_from(py_file: Path, prefix: str) -> set[str]:
    """Collect FastAPI paths out of a module, with its router prefix applied.

    Handles both `@router.<verb>("...")` (our modules) and `@app.<verb>("...")`
    (the repo's own dashboard).
    """
    if not py_file.is_file():
        return set()
    text = py_file.read_text(encoding="utf-8", errors="replace")
    out = set()
    pattern = r'@(?:router|app)\.(?:get|post|delete|put)\("([^"]*)"\)'
    for match in re.finditer(pattern, text):
        out.add(prefix + match.group(1))
    return out


def js_api_paths() -> dict[str, set[str]]:
    """Normalise every API path the UI calls, per file."""
    found: dict[str, set[str]] = {}
    for name in JS_FILES:
        path = UI / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        calls = set()
        for match in re.finditer(r"""(?:api|fetch)\(\s*[`'"]([^`'"]+)[`'"]""", text):
            raw = match.group(1)
            if not raw.startswith("/api"):
                continue
            raw = raw.split("?")[0]
            # Template holes may contain nested braces ({ (st || {}).symbol }), so match
            # one level of nesting — a naive [^}]+ stops early and invents a bogus path.
            raw = re.sub(r"\$\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", "{param}", raw)
            raw = re.sub(r"'\s*\+[^+]*\+\s*'", "{param}", raw)     # 'a' + x + 'b'
            raw = re.sub(r"\"\s*\+[^+]*\+\s*\"", "{param}", raw)
            raw = re.split(r"[$`\s]", raw)[0] or raw               # nested template tail
            calls.add(raw.rstrip("/") or "/")
        found[name] = calls
    return found


def normalise(route: str) -> str:
    return re.sub(r"\{[^}]+\}", "{param}", route).rstrip("/")


def js_syntax_check() -> list[str]:
    """Parse every front-end module with node --check.

    A syntax error here is invisible at runtime: the browser drops the whole
    module, the app looks healthy, and one entire feature set is simply missing.
    That is exactly how a stray apostrophe inside a single-quoted string killed
    the guide module, so it belongs in the end-of-build audit.
    """
    import pathlib
    import shutil
    import subprocess

    node = shutil.which("node")
    ui = pathlib.Path(__file__).resolve().parents[1] / "orderflow_system" / "desktop" / "ui"
    extra = list((ui / "indicators").glob("*.js")) if (ui / "indicators").is_dir() else []
    files = [f for f in sorted(list(ui.glob("*.js")) + extra) if "vendor" not in f.parts]
    if not node:
        return ["(node not found — JS syntax check skipped)"]
    bad = []
    for f in files:
        proc = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        if proc.returncode != 0:
            first = (proc.stderr or "").strip().splitlines()
            detail = next((ln for ln in first if "SyntaxError" in ln), first[0] if first else "unknown")
            bad.append(f"{f.name}: {detail.strip()}")
    if not bad:
        print(f"5. js syntax: {len(files)} module(s) parse cleanly")
    return bad


def main() -> int:
    problems: list[str] = []

    routes = set()
    routes |= routes_from(ROOT / "orderflow_system" / "atlas" / "api.py", "/api/atlas")
    routes |= routes_from(ROOT / "orderflow_system" / "desktop" / "api.py", "/api/control")
    routes |= routes_from(ROOT / "orderflow_system" / "desktop" / "edgar.py", "/api/fundamentals")
    # §147: the feature routers the launcher mounts beside the original api modules.
    routes |= routes_from(ROOT / "orderflow_system" / "atlas" / "footprint_config.py", "/api/atlas")
    routes |= routes_from(ROOT / "orderflow_system" / "atlas" / "depth_history.py", "/api/atlas")
    routes |= routes_from(ROOT / "orderflow_system" / "atlas" / "dataquality.py", "/api/atlas")
    routes |= routes_from(ROOT / "orderflow_system" / "atlas" / "sessions.py", "/api/atlas")
    routes |= routes_from(ROOT / "orderflow_system" / "atlas" / "derivatives.py", "/api/atlas")
    routes |= routes_from(ROOT / "orderflow_system" / "atlas" / "synthetic.py", "/api/atlas")
    routes |= routes_from(ROOT / "orderflow_system" / "desktop" / "orders.py", "/api/control")
    routes |= routes_from(ROOT / "orderflow_system" / "dashboard" / "app.py", "")
    known = {normalise(r) for r in routes}

    def resolves(call: str) -> bool:
        """A JS call resolves if it matches a route, or that route plus one or two
        segments (the common `'/api/atlas/cvd/' + symbol` / frames + frame shapes)."""
        norm = normalise(call)
        if norm in known:
            return True
        return any(norm + "/{param}" * n in known for n in (1, 2))

    print(f"1. routes discovered: {len(routes)}")

    for name, calls in js_api_paths().items():
        for call in sorted(calls):
            if resolves(call):
                continue
            problems.append(f"   MISSING ROUTE  {name}: {call}")

    # 2. element ids — every page the UI serves (§148 T5-F-17: monitor.js styles `monStatus`,
    # which lives in monitor.html; scanning only index.html never saw it).
    html_ids = set()
    index = UI / "index.html"
    for page in sorted(UI.glob("*.html")):
        html_ids |= set(re.findall(r'id="([A-Za-z0-9_-]+)"',
                                   page.read_text(encoding="utf-8", errors="replace")))
    created_ids: set[str] = set()
    for name in JS_FILES:
        path = UI / name
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            created_ids |= set(re.findall(r"""id=["'`]([A-Za-z0-9_-]+)["'`]""", text))
            created_ids |= set(re.findall(r"""id=\\?["']([A-Za-z0-9_-]+)\\?["']""", text))
            created_ids |= set(re.findall(r"""\.id\s*=\s*['"]([A-Za-z0-9_-]+)['"]""", text))
    all_ids = html_ids | created_ids

    used_ids: set[str] = set()
    # §148 T5-F-17: every module in JS_FILES owns element ids (§147's new panels among them) and
    # none of them was ever checked against the pages — walk the same list the created-ids pass
    # does. The widened scan is what surfaced `logBody`, `inCard` and `monStatus`.
    for name in JS_FILES:
        path = UI / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        used_ids |= set(re.findall(r"""getElementById\(['"]([A-Za-z0-9_-]+)['"]\)""", text))
        used_ids |= set(re.findall(r"""\$\(['"]#([A-Za-z0-9_-]+)['"]\)""", text))
    missing_ids = sorted(i for i in used_ids if i not in all_ids)
    print(f"2. ids used by modules: {len(used_ids)} | html {len(html_ids)} + created {len(created_ids)}"
          f" | missing: {len(missing_ids)}")
    for i in missing_ids:
        problems.append(f"   MISSING ELEMENT  {i}")

    # 3. duplicate ids in index.html
    if index.is_file():
        raw = index.read_text(encoding="utf-8", errors="replace")
        seen: dict[str, int] = {}
        for i in re.findall(r'id="([A-Za-z0-9_-]+)"', raw):
            seen[i] = seen.get(i, 0) + 1
        dups = {k: v for k, v in seen.items() if v > 1}
        print(f"3. duplicate ids in index.html: {len(dups)} {dups if dups else ''}")
        for k, v in dups.items():
            problems.append(f"   DUPLICATE ID  {k} x{v}")

    # 4. import check
    sys.path.insert(0, str(ROOT))
    try:
        import orderflow_system.atlas.api as atlas_api          # noqa: F401
        import orderflow_system.desktop.api as desktop_api      # noqa: F401
        import orderflow_system.atlas.history as history        # noqa: F401
        import orderflow_system.atlas.notify as notify          # noqa: F401
        import orderflow_system.atlas.imbalance as imbalance    # noqa: F401
        import orderflow_system.atlas.services as services      # noqa: F401
        print("4. modules import: ok")
    except Exception as exc:                                     # pragma: no cover
        problems.append(f"   IMPORT FAILED  {type(exc).__name__}: {exc}")
        print(f"4. modules import: FAILED ({exc})")
        print(f"   interpreter: {sys.executable}")
        if isinstance(exc, ModuleNotFoundError):
            print("   hint: this audit imports the package — run it with the project venv, e.g.")
            print("         .venv/Scripts/python.exe scripts/audit_ui_refs.py")

    syntax_bad = js_syntax_check()
    for item in syntax_bad:
        if item.startswith("("):
            print(f"5. {item}")
        else:
            problems.append(f"js syntax: {item}")
    if any(not i.startswith("(") for i in syntax_bad):
        print(f"5. js syntax: {len([i for i in syntax_bad if not i.startswith('(')])} module(s) FAILED to parse")

    print()
    if problems:
        print("PROBLEMS FOUND:")
        print("\n".join(sorted(set(problems))))
        return 1
    print("AUDIT CLEAN — no broken calls or dead element references.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
