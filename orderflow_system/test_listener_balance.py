"""Listener balance per UI module: an add must be paired with a removal, or the module must be
on the frozen allow-list with its count (G-03, half b).

The v0.1b audit's teardown contract was "activate then deactivate leaves the stub's registry
empty". This codebase's UI modules are page-lifetime: most register their document/window
listeners once at boot and are never torn down, so the honest pin is structural — a module whose
addEventListener count exceeds its removeEventListener count must be listed below with its count,
or the test fails. The allow-list numbers are frozen: they can only go down, and a new unbalanced
listener in an allow-listed module still fails.

(The runtime half of G-03 — per-node identity, detector B/C from the audit's receipts — is the
churn probe, scripts/churn_probe.py, which CI runs against the frozen app; see the probe's CI job.)
"""

from __future__ import annotations

import re
from pathlib import Path

UI = Path(__file__).parent / "desktop" / "ui"

ADD = re.compile(r"addEventListener\s*\(")
REMOVE = re.compile(r"removeEventListener\s*\(")

#: module -> (adds, removes) as measured when this guard landed. add - remove may only shrink.
FROZEN_UNBALANCED = {
    "alpaca-card.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "atlas-v2.js": (5, 0),   # boot-time listener(s) with no teardown path; frozen
    "atlas.js": (16, 0),   # boot-time listeners; +2 are the B5 dim/highlight dials (§118); frozen
    "audio.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "calendar.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "chrome.js": (3, 0),   # boot-time listener(s) with no teardown path; frozen
    "colrail.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "context.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "drawings.js": (18, 2),   # 18 adds vs 2 removes reachable today; frozen
    "freshness.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "fundamentals.js": (4, 0),   # boot-time listener(s) with no teardown path; frozen
    "guide.js": (3, 0),   # boot-time listener(s) with no teardown path; frozen
    "heatmap-pro.js": (12, 0),   # boot-time listener(s) with no teardown path; frozen
    "help.js": (7, 0),   # boot-time listener(s) with no teardown path; frozen
    "hint.js": (13, 0),   # boot-time listener(s) with no teardown path; frozen
    "inbox.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "intent.js": (5, 0),   # boot-time listener(s) with no teardown path; frozen
    "journal.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "keys.js": (2, 0),   # boot-time listener(s) with no teardown path; frozen
    "links.js": (6, 0),   # boot-time listener(s) with no teardown path; frozen
    "lookup.js": (5, 0),   # boot-time listener(s) with no teardown path; frozen
    "market-pressure.js": (3, 0),   # boot-time listener(s) with no teardown path; frozen
    # 4/0: §117's rebind capture — one more page-lifetime keydown listener in the menu, in the
    # capture phase and inert unless the user is choosing a combination (it must run before
    # the dispatcher, so it cannot live in the registry).
    "menu.js": (4, 0),   # boot-time listener(s) with no teardown path; frozen
    # 21/0: the menu subscribes to the profile store's own "something changed" event so its
    # Profiles group cannot drift from the view. Page-lifetime, like the module's other 20.
    "menubar.js": (21, 0),   # boot-time listener(s) with no teardown path; frozen
    "news.js": (3, 0),   # boot-time listener(s) with no teardown path; frozen
    "ofx-view.js": (32, 0),   # boot-time listener(s) with no teardown path; frozen
    "ofx.js": (9, 1),   # 9 adds vs 1 removes reachable today; frozen
    "options.js": (6, 0),   # boot-time listener(s) with no teardown path; frozen
    "paper.js": (2, 0),   # boot-time listener(s) with no teardown path; frozen
    "pause.js": (2, 0),   # boot-time listener(s) with no teardown path; frozen
    "platforms.js": (17, 0),   # boot-time listener(s) with no teardown path; frozen
    "profiles.js": (3, 0),   # boot-time listener(s) with no teardown path; frozen
    "scale.js": (3, 0),   # boot-time listener(s) with no teardown path; frozen
    "scopes.js": (4, 0),   # boot-time listener(s) with no teardown path; frozen
    "search.js": (5, 0),   # boot-time listener(s) with no teardown path; frozen
    "settings-pro.js": (10, 0),   # boot-time listener(s) with no teardown path; frozen
    "shell.js": (17, 3),   # 17 adds vs 3 removes reachable today; frozen
    "steady.js": (5, 0),   # boot-time listener(s) with no teardown path; frozen
    "storage.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "strips.js": (10, 0),   # boot-time listener(s) with no teardown path; frozen
    "studies.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "table.js": (7, 1),   # 7 adds vs 1 removes reachable today; frozen
    "templates.js": (3, 0),   # boot-time listener(s) with no teardown path; frozen
    "theme.js": (3, 0),   # boot-time listener(s) with no teardown path; frozen
    "ui.js": (8, 0),   # boot-time listener(s) with no teardown path; frozen
    "updates.js": (2, 0),   # boot-time listener(s) with no teardown path; frozen
    "watchlist.js": (4, 0),   # boot-time listener(s) with no teardown path; frozen
    "watermark.js": (2, 0),   # boot-time listener(s) with no teardown path; frozen
    "windowing.js": (3, 0),   # boot-time listener(s) with no teardown path; frozen
    "windows-ui.js": (3, 1),   # 3 adds vs 1 removes reachable today; frozen
}


def _counts() -> dict[str, tuple[int, int]]:
    measured = {}
    for path in sorted(UI.glob("*.js")):
        if path.name.endswith(".selftest.js"):
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        measured[path.name] = (len(ADD.findall(src)), len(REMOVE.findall(src)))
    return measured


def test_every_listener_is_paired_or_frozen_with_its_count():
    measured = _counts()
    regressions: list[str] = []
    for name, (adds, removes) in measured.items():
        if adds <= removes:
            continue                                  # paired: nothing to excuse
        frozen = FROZEN_UNBALANCED.get(name)
        if frozen is None:
            regressions.append(f"{name}: {adds} add / {removes} remove — not on the allow-list")
        elif adds > frozen[0] or removes < frozen[1]:
            regressions.append(
                f"{name}: {adds} add / {removes} remove — frozen at {frozen[0]}/{frozen[1]} "
                "(the surface may only shrink)")
    assert not regressions, ("unpaired listener(s) — pair it, or freeze a lower count with a "
                             "reason:\n" + "\n".join(regressions))


def test_the_allow_list_still_describes_the_tree():
    """A stale entry (a module that is now balanced or gone) must be removed, not left to rot."""
    measured = _counts()
    stale = [name for name in FROZEN_UNBALANCED
             if name not in measured or measured[name][0] <= measured[name][1]]
    assert not stale, f"allow-list entries no longer needed: {stale}"
