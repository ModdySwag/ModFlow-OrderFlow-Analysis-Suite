"""Wiring guards for index.html — the one failure this suite cannot survive quietly.

Every panel in this app is a `<section class="view" data-view="X">` plus a nav item plus a script tag,
and the module loader treats a script that fails to load as FATAL: it renders its "module error" banner
and replaces the shell, so a single tag with no file behind it takes the whole UI down (measured — the
page came up with `views: 0` and an empty body). Nothing else in the suite fails that way, which is why
this file exists: the wiring is checked as data, before a browser ever sees it.

It is deliberately dumb — read index.html, look at what it claims, look at the disk. No browser, no
imports from the app, no fixtures.
"""

from __future__ import annotations

import re
from pathlib import Path


UI = Path(__file__).parent / "desktop" / "ui"
INDEX = UI / "index.html"
ROOT = Path(__file__).resolve().parents[1]

_APP = None


def _desktop_app():
    """The desktop app for the served-page checks.

    `build_app()` may run once per process: the FastAPI app it decorates is a module-level
    singleton, and a second `add_middleware` raises "Cannot add middleware after an application
    has started" once any client has exercised it. Both served-page tests share this build, so
    they hold in any order.
    """
    global _APP
    if _APP is None:
        from orderflow_system.desktop.launcher import build_app

        _APP = build_app(8099)
    return _APP


def _html() -> str:
    return INDEX.read_text(encoding="utf-8", errors="replace")


def _local_scripts(html: str) -> list[str]:
    """Script tags this app serves itself, as paths relative to ui/ (vendor bundles live in a subfolder)."""
    srcs = re.findall(r'<script[^>]+src="([^"]+)"', html)
    return [s[len("/desktop/"):] for s in srcs if s.startswith("/desktop/")]


def _views(html: str) -> list[str]:
    return re.findall(r'<section class="view"[^>]*data-view="([a-z0-9_-]+)"', html)


def _nav(html: str) -> list[str]:
    return re.findall(r'class="nav-item"[^>]*data-view="([a-z0-9_-]+)"', html)


def test_the_cursor_link_and_the_ladder_agree_on_the_price_attribute():
    """The engine draws a trace into the ladder by reading each row's price attribute, so the
    attribute the consumer queries must exist in the producer's row markup.

    Measured the hard way: the consumer asked for `[data-price]`, the ladder never set it, so no row
    could ever be highlighted and the view's note always read 'outside the drawn ladder levels' —
    which looked like a coordinate problem and was a wiring problem.
    """
    view = (UI / "ofx-view.js").read_text(encoding="utf-8", errors="replace")
    found = re.search(r"querySelectorAll\('\[(data-[a-z-]+)\]'\)", view)
    assert found, "ofx-view.js no longer looks ladder rows up by a data attribute — update this guard"
    attr = found.group(1)
    ladder = (ROOT / "orderflow_system" / "dashboard" / "static" / "orderbook.js").read_text(
        encoding="utf-8", errors="replace")
    assert attr + "=" in ladder, (
        "the cursor link highlights ladder rows by '" + attr + "', but the ladder's row markup never "
        "sets it — the highlight can never match")
    assert "ofx-traced" in ladder, (
        "the ladder must re-apply the cursor highlight inside its own render — it rebuilds its rows on "
        "every update, so a class painted by the consumer is wiped by the next poll")
    assert "nearest(prices, null)" not in view, (
        "the cursor link must bound its match to the ladder's own step — a null tolerance accepts any "
        "distance, so a price well outside the drawn band was announced as 'on the ladder'")


def test_the_appearance_layer_is_wired():
    """Theme, accent and density: the stylesheets, the pre-paint mirror, the module and its controls.

    The appearance is applied by an attribute on <html> and painted before the body exists (an
    appearance that lands a frame late is a flash), so all four parts have to be present: the files
    that define the tokens, the script that reads the mirror before paint, the module that reads the
    config, and the switches that write both.
    """
    html = _html()
    for name in ("dark", "light", "contrast", "accents", "density"):
        assert (UI / "themes" / f"{name}.css").is_file(), f"themes/{name}.css is missing"
        assert f'href="/desktop/themes/{name}.css"' in html, f"themes/{name}.css is not loaded"
        text = (UI / "themes" / f"{name}.css").read_text(encoding="utf-8", errors="replace")
        assert "--of-" in text, f"themes/{name}.css declares no tokens"
    assert (UI / "theme.js").is_file() and '<script src="/desktop/theme.js"></script>' in html
    assert "ofap.appearance" in html, "the pre-paint mirror is not read in <head>"
    for control in ("setTheme", "setAccent", "setDensity"):
        assert f'id="{control}"' in html, f"{control} is not in Settings"


def test_no_raw_colour_lives_outside_the_token_block():
    """The brief's grep gate as a test: the shell themes by swapping tokens, so a rule that hard-codes
    a colour is a rule that stays dark in the light shell."""
    files = [UI / "atlas.css", UI / "ui.css", UI / "modules.css"] + sorted((UI / "themes").glob("*.css"))
    offenders = []
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if re.search(r"#[0-9a-fA-F]{3,8}\b", line) and "--of-" not in line:
                offenders.append(f"{path.name}:{number}: {line.strip()[:90]}")
    assert not offenders, "raw colours outside the token block:\n" + "\n".join(offenders[:10])


def test_every_script_tag_resolves_to_a_file():
    """A tag with no file behind it is the one thing that empties the UI — so it is a test, not a habit."""
    html = _html()
    tags = _local_scripts(html)
    assert len(tags) >= 20, f"only {len(tags)} local script tags found — is index.html intact?"
    missing = [src for src in tags if not (UI / src).is_file() and not (UI / "vendor" / src).is_file()]
    assert not missing, (
        "index.html loads a module that does not exist on disk — this takes the whole shell down at "
        f"boot (the loader's error path replaces the page): {missing}")


def test_every_view_has_a_nav_item_and_a_script_that_claims_it():
    """A section nobody can navigate to, or that no module watches, is dead weight either way."""
    html = _html()
    views = _views(html)
    nav = set(_nav(html))
    assert len(views) >= 20, f"only {len(views)} views found"
    assert len(views) == len(set(views)), "two sections share a data-view"
    without_nav = [v for v in views if v not in nav]
    assert not without_nav, f"views with no nav item: {without_nav}"
    scripts = {}
    for src in _local_scripts(html):
        path = UI / src if (UI / src).is_file() else UI / "vendor" / src
        if path.is_file():
            scripts[src.rsplit("/", 1)[-1]] = path.read_text(encoding="utf-8", errors="replace")
    unclaimed = []
    for view in views:
        marker = 'data-view="%s"' % view
        if marker not in html:
            unclaimed.append(view)
            continue
        # the module that owns a view names it in its own source (the observer's filter/element lookup)
        if not any(('data-view="%s"' % view) in text or ("'%s'" % view) in text for text in scripts.values()):
            unclaimed.append(view)
    assert not unclaimed, f"no loaded module mentions these views: {unclaimed}"


def test_the_sections_the_recent_panels_added_are_all_present():
    """The panels built since this guard existed — one line each, so a refactor cannot quietly drop one."""
    html = _html()
    for view in ("watchlist", "news", "options", "fundamentals"):
        assert 'data-view="%s"' % view in html, f"{view} section is gone from index.html"
        assert (UI / f"{view}.js").is_file(), f"{view}.js is gone"
        assert f'<script src="/desktop/{view}.js"></script>' in html, f"{view}.js is not loaded"


def test_ordering_the_modules_depend_on():
    """bus.js must load before the panels that subscribe to it, and shell/links before the shell's users."""
    html = _html()
    order = [s.rsplit("/", 1)[-1] for s in _local_scripts(html)]
    for later in ("shell.js", "links.js", "bus.js"):
        assert later in order, f"{later} is not loaded at all"
    for panel in ("watchlist.js", "news.js", "options.js", "fundamentals.js"):
        if panel in order:
            assert order.index("bus.js") < order.index(panel), f"{panel} loads before bus.js"


def test_the_audit_lists_every_panel_module():
    """A module the audit does not scan is a module whose element ids are unchecked."""
    audit = (ROOT / "scripts" / "audit_ui_refs.py").read_text(encoding="utf-8", errors="replace")
    for panel in ("watchlist.js", "news.js", "options.js", "fundamentals.js", "shell.js", "links.js", "bus.js",
                  "keys.js", "freshness.js"):
        assert f'"{panel}"' in audit, f"{panel} is missing from JS_FILES"


def test_panels_scope_their_section_lookup_to_the_view_element():
    """A bare [data-view="x"] matches the NAV BUTTON first (it comes earlier in the document), so a panel
    would watch the button instead of its section — measured in terminal mode, where no nav button is
    ever .active and the panel therefore believed it was off-screen and paused. All five panels must
    scope the lookup to the section."""
    offenders = []
    for name in ("watchlist.js", "news.js", "options.js", "fundamentals.js", "platforms.js"):
        text = (UI / name).read_text(encoding="utf-8", errors="replace")
        for bad in ("querySelector('[data-view=", 'querySelector("[data-view='):
            if bad in text:
                offenders.append(name)
                break
    assert not offenders, f"section lookup not scoped to .view: {offenders}"

# ──────────────────────────────────────────────────────────────
# P3-3 (R7): the legacy page is retired behind the desktop shell
# ──────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────
# secure2 sweep: the shell's Content-Security-Policy
# ──────────────────────────────────────────────

def test_the_shell_carries_a_csp_that_forbids_remote_hosts():
    """The shell is self-contained (every script/style/image is same-origin, no CDN, no web
    font, no iframe), so its CSP must not allow any remote target — while keeping only the one
    allowance the app genuinely needs: the Studies engine's `new Function` compilation of
    user-pasted modules. The inline pre-paint script is allowed by HASH (SEC-08) — the exact
    hash is pinned in test_security_fixes.py."""
    import re as _re

    match = _re.search(r'http-equiv="Content-Security-Policy"\s+content="([^"]+)"', _html())
    assert match, "the shell lost its Content-Security-Policy"
    policy = match.group(1)
    for directive in ("default-src 'self'", "script-src 'self'",
                      "style-src 'self' 'unsafe-inline'", "object-src 'none'",
                      "frame-src 'none'", "base-uri 'none'", "form-action 'self'"):
        assert directive in policy, f"CSP lost {directive!r}: {policy}"
    assert "'unsafe-inline'" not in policy.split(";")[1], "script-src must not allow all inline"
    for loopback_ws in ("ws://127.0.0.1:*", "ws://localhost:*"):
        assert loopback_ws in policy, f"CSP must allow the app's own stream {loopback_ws!r}: {policy}"
    # the only permitted wildcard is the loopback WS port; everything else is closed
    without_ws = _re.sub(r"ws://[^;\s]+", "", policy)
    assert "*" not in without_ws, f"a non-loopback wildcard crept into the CSP: {policy}"
    assert "http:" not in without_ws and "https:" not in without_ws, \
        f"a remote source crept into the CSP: {policy}"


# ──────────────────────────────────────────────
# secure2 sweep — the loopback request guard's wiring (behaviour lives in test_request_guard)
# ──────────────────────────────────────────────

def test_the_app_registers_the_loopback_request_guard_middleware():
    """The guard must be attached at app level, not only mentioned: a rebinding Host or a
    cross-site mutation is refused before any endpoint runs (test_request_guard.py pins the
    behaviour; this pins that the middleware is actually in the stack)."""
    from orderflow_system.dashboard.app import LocalRequestGuard

    app = _desktop_app()
    stacks = [entry for entry in app.user_middleware if entry.cls is LocalRequestGuard]
    assert stacks, "LocalRequestGuard is not in the application middleware stack"


def test_the_repo_ships_a_security_policy():
    """A public release needs a disclosure path: without SECURITY.md, a reporter's only
    obvious door is a public issue — the worst place for a live vulnerability."""
    policy = ROOT / "SECURITY.md"
    assert policy.is_file(), "SECURITY.md (responsible disclosure) is missing"
    text = policy.read_text(encoding="utf-8")
    assert "Report a vulnerability" in text, "SECURITY.md must name the private reporting route"
    assert "127.0.0.1" in text, "SECURITY.md must state the loopback-only model"


def test_legacy_root_redirects_to_the_desktop_shell():
    """`GET /` must hand the browser to /desktop (307, method-preserving), and /desktop must
    answer with the desktop shell itself — the legacy terminal page is no longer the front
    door. The redirect is one block in launcher.build_app, reversible by deleting it."""
    from fastapi.testclient import TestClient

    client = TestClient(_desktop_app())
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 307, res.status_code
    assert res.headers.get("location") == "/desktop"

    shell = client.get("/desktop", follow_redirects=True)
    assert shell.status_code == 200
    assert "ModFlow OrderFlow Analysis Suite" in shell.text
    assert "Orderflow Trading Terminal" not in shell.text
# ──────────────────────────────────────────────────────────────
# P62: the rail brand — the mark is the badge icon, the wording reads sentence case
# ──────────────────────────────────────────────────────────────

def test_rail_brand_mark_is_the_badge_icon_and_the_wording_reads_sentence_case():
    """P62: the rail's top-left mark is the badge icon asset (a real file, served by the desktop
    mount) instead of the old text tile, and the subtitle is sentence case — the all-caps
    transform is gone from the stylesheet that styles it."""
    page = _html()
    assert 'class="brand-mark" src="/desktop/brand-icon.png"' in page
    assert ">MF<" not in page, "the rail mark is the icon now; a text tile is a regression"
    assert '<span class="brand-sub">Orderflow Analysis Suite</span>' in page
    assert (UI / "brand-icon.png").is_file(), "the mark must be a real asset on disk"

    css = (UI / "ui.css").read_text(encoding="utf-8", errors="replace")
    sub_rule = css.split(".brand-sub", 1)[1].split("}", 1)[0]
    assert "uppercase" not in sub_rule, "the rail sub must read sentence case (P62 wording modernisation)"

    from fastapi.testclient import TestClient

    res = TestClient(_desktop_app()).get("/desktop/brand-icon.png")
    assert res.status_code == 200, res.status_code
    # The bytes, not the header: on Windows the served content-type comes from the host's MIME
    # database (mimetypes reads HKCR — a host whose ".png\Content Type" is empty makes 3.11 answer
    # application/octet-stream while 3.12 falls back to image/png), so byte identity is both the
    # stronger check and the host-independent one.
    assert res.content == (UI / "brand-icon.png").read_bytes(), "the mount serves the mark itself"


def test_unknown_symbols_serve_nothing_from_the_demo_fillers():
    """v0.1b Tier 8 #2: with no engine running, /api/footprint and /api/tape must serve an
    UNKNOWN symbol NOTHING — not the old invented $1,000 chart. The models_symbol guard
    applies to the no-engine branch exactly as it does to the warming branch (an engine
    running with a symbol that has not printed yet). Modeled symbols keep their demo fill."""
    from fastapi.testclient import TestClient

    client = TestClient(_desktop_app())

    assert client.get("/api/footprint/UNKNOWNXYZ").json() == [], "no invented chart"
    assert client.get("/api/tape/UNKNOWNXYZ?count=5").json() == [], "no invented prints"

    # the demo fill itself must not regress for symbols the generator models
    assert len(client.get("/api/footprint/BTCUSDT").json()) > 0
    assert len(client.get("/api/tape/BTCUSDT?count=5").json()) > 0


# ──────────────────────────────────────────────────────────────
# §76: a module-local `api()` must name the shell's helper (window.api)
# ──────────────────────────────────────────────────────────────

def test_a_module_local_api_helper_must_name_the_shells_helper():
    """A module-local `function api(...)` that guards with `typeof api === 'function'` is checking
    itself: the guard is always true, the call recurses, and the RangeError lands in the caller's
    `catch` — so the module silently runs on its fallback data.

    Measured live on the ☰ menu (§76): `/api/control/sources` never loaded (`state.sources` stayed
    empty), the Connections list painted its hardcoded fallback with every source looking usable,
    and switching anything answered "source switch failed: RangeError: Maximum call stack size
    exceeded". menubar.js does it right (`typeof window.api`); this pins the rule for every module:
    name the shell's helper, never the local one.
    """
    offenders = []
    for path in sorted(UI.glob("*.js")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"function\s+api\s*\(", text) \
                and re.search(r"typeof\s+api\s*===\s*['\"]function", text):
            offenders.append(path.name)
    assert not offenders, (
        f"{offenders} declares a local api() and then tests the bare name — which resolves to that "
        "same function. The guard must read `typeof window.api` (the shell's helper in ui.js).")


# ──────────────────────────────────────────────────────────────
# v0.1.0-beta shake-down: the frozen build must ship every asset root the shell loads
# ──────────────────────────────────────────────────────────────

def test_the_frozen_build_ships_every_asset_root_the_shell_loads():
    """index.html loads assets from /desktop/ AND /static/ — the repo must have them and the
    frozen build must ship both directories.

    Measured on the first v0.1.0-beta exe (2026-09-17, during the final-security-audit pass):
    build_exe.py shipped `desktop/ui` but not `dashboard/static`, so `/static/footprint.js`,
    `/static/orderbook.js`, `/static/tape.js`, `/static/signals.js`, `/static/performance.js` and
    `/static/microstructure.js` all answered 404 in the frozen app: `window.FootprintChart`,
    `window.OrderbookLadder`, `window.TimeAndSales`, `window.SignalCards`,
    `window.PerformanceDashboard` and `window.MicrostructurePanel` stayed undefined and those six
    widgets silently never initialised (the Tape view rendered 0 rows live). The repo tree was
    fine, and the script-tag guard above only looks at /desktop/ — which is exactly why nothing
    caught it. This pins both halves: the referenced files exist on disk, and every root the page
    loads from is inside the build's REQUIRED_DATA_RELS.
    """
    import importlib.util

    html = _html()
    refs = re.findall(r'(?:src|href)="([^"]+)"', html)
    local = [r for r in refs
             if not r.startswith(("http://", "https://", "data:", "#", "mailto:", "//")) and r != "/"]
    roots = {"/desktop/": UI,
             "/static/": ROOT / "orderflow_system" / "dashboard" / "static"}
    unknown_roots = [r for r in local if not any(r.startswith(p) for p in roots)]
    assert not unknown_roots, (
        f"index.html loads from an asset root this guard does not know: {unknown_roots} — add it "
        "here and make sure the frozen build ships it")
    missing = [r for r in local
               for prefix, base in roots.items()
               if r.startswith(prefix) and not (base / r[len(prefix):].split("?")[0]).is_file()]
    assert not missing, f"index.html loads files that are not on disk: {missing}"

    spec = importlib.util.spec_from_file_location("ofap_build_exe", ROOT / "scripts" / "build_exe.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    shipped = set(getattr(mod, "REQUIRED_DATA_RELS", ()))
    for prefix, base_rel in (("/desktop/", mod.UI_REL), ("/static/", mod.STATIC_REL)):
        if any(r.startswith(prefix) for r in local):
            assert base_rel in shipped, (
                f"the shell loads assets from {prefix} ({base_rel}) but the frozen build does not "
                "ship that directory (REQUIRED_DATA_RELS) — the packaged app 404s them silently")
def test_the_engine_view_poll_only_runs_while_its_view_is_shown():
    """Hidden panels age by design: the ofx engine poll (five endpoints per 2.5 s) used to keep
    asking behind every other view. The gate must scope its lookup like every other panel."""
    src = (UI / "ofx-view.js").read_text(encoding="utf-8")
    assert '.view[data-view="ofx"]' in src, "the poll must scope its own section (not a bare data-view)"
    assert "classList.contains('active')" in src, "the poll must check that the view is the shown one"


def test_the_panel_loaders_keep_their_request_sequencing():
    """Only the newest load may paint (audit B-JS-01/02).

    `loadChart`/`loadOrderbook`/`loadTape` (ui.js) and the Engine view's `load()` (ofx-view.js)
    each capture a sequence token before their fetches and bail once a newer request has started.
    Two overlapping loads resolve in either order, so without the guard a stale payload repaints
    the panel for the previous instrument. This is the regression pin for that guard, plus the
    top-bar↔Engine symbol bridge (B-JS-03) and the pointer-leave hover clear (C-07 / B-JS-04).
    """
    ui = (UI / "ui.js").read_text(encoding="utf-8")
    view = (UI / "ofx-view.js").read_text(encoding="utf-8")
    engine = (UI / "ofx.js").read_text(encoding="utf-8")

    assert "let chartSeq = 0;" in ui and "seq !== chartSeq" in ui
    assert "seq !== bookSeq" in ui and "seq !== tapeSeq" in ui
    assert "let loadSeq = 0;" in view and "seq !== loadSeq" in view
    # the symbol bridge between the top bar and the Engine head
    assert "ofap:symbol" in ui and "ofap:symbol" in view and "function syncTopBar(" in view
    # leaving the canvas clears the crosshair/tooltip state
    assert "canvas.addEventListener('mouseleave'" in engine
    assert "state.hover = null;" in engine
