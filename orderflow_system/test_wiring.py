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

import pytest

UI = Path(__file__).parent / "desktop" / "ui"
INDEX = UI / "index.html"
ROOT = Path(__file__).resolve().parents[1]


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
    for panel in ("watchlist.js", "news.js", "options.js", "fundamentals.js", "shell.js", "links.js", "bus.js"):
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
