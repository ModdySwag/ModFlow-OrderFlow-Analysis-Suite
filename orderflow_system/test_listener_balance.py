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
    # 3/0: §147 the Condition builder card — the delegated click and change on the card body plus the
    # DOMContentLoaded boot. Page-lifetime by design, no timers: it reads on activation and on demand.
    "alert-builder.js": (3, 0),
    # 4/0: §147 the data-quality cockpit — recheck, the watchlist select, the rows' delegated click and
    # the boot; its poller is on the pause registry.
    "data-quality.js": (4, 0),
    # 4/0: §147 Funding and open interest — refresh, venue apply, the shell's instrument switch, boot;
    # its poller is on the pause registry.
    "derivatives.js": (4, 0),
    # 3/0: §147 the read-only companion page — the tab/watchlist click on <body>, visibilitychange and
    # the boot; its poller is on the pause registry and checks document.hidden itself.
    "monitor.js": (3, 0),
    # 3/0: §147 Sessions — the delegated click and change on the host, plus the boot; the 1 Hz clock
    # face is registered with OFAPPause.
    "sessions.js": (3, 0),
    # 3/0: §147 Synthetic — one delegated click and one delegated change on its own card, plus the boot;
    # its poller is on the pause registry.
    "synthetic.js": (3, 0),
    # 2/0: §148 — one DOMContentLoaded boot, plus one pagehide teardown that tells the card
    # observer to let go of the document instead of holding it for the tab's life (T7-F14); the
    # walk itself is filtered by worthWalking, so a plain repaint costs nothing. No timers.
    "why.js": (2, 0),
    "alpaca-card.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "atlas-v2.js": (5, 0),   # boot-time listener(s) with no teardown path; frozen
    "atlas.js": (18, 0),   # boot-time listeners; +2 are the B5 dim/highlight dials (§118); +2 the
                           # §129 replay instrument picker (a focus re-read, and the switcher's own
                           # announcement refreshing the list); frozen
    "audio.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "calendar.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "chrome.js": (3, 0),   # boot-time listener(s) with no teardown path; frozen
    "colrail.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "context.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "drawings.js": (18, 2),   # 18 adds vs 2 removes reachable today; frozen
    "freshness.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    # 4/0: §146's Settings ▸ Feed keys card — the DOMContentLoaded boot, the rows' delegated click,
    # and the two lane selects (they save the moment they change); page-lifetime by design, no timers.
    "feedkeys.js": (4, 0),
    "fundamentals.js": (4, 0),   # boot-time listener(s) with no teardown path; frozen
    # 5/0: §136's GEX panel — refresh button, chain-source select, symbol box, the shell's own
    # instrument switch, plus the DOMContentLoaded boot. Page-lifetime like the panels above, and
    # its poller is registered with OFAPPause (so P clears it) rather than torn down by hand.
    "gex.js": (5, 0),
    "guide.js": (4, 0),   # 3 + the section 123 overlay keyboard layer (one document keydown); boot-time, frozen
    "heatmap-pro.js": (15, 0),   # 12 + §120 adoption + window drag + §122 Detail dial; boot-time, frozen
    "help.js": (7, 0),   # boot-time listener(s) with no teardown path; frozen
    "hint.js": (13, 0),   # boot-time listener(s) with no teardown path; frozen
    "inbox.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "intent.js": (5, 0),   # boot-time listener(s) with no teardown path; frozen
    "journal.js": (1, 0),   # boot-time listener(s) with no teardown path; frozen
    "keys.js": (2, 0),   # boot-time listener(s) with no teardown path; frozen
    "links.js": (6, 0),   # boot-time listener(s) with no teardown path; frozen
    "lookup.js": (5, 0),   # boot-time listener(s) with no teardown path; frozen
    "market-pressure.js": (3, 0),   # boot-time listener(s) with no teardown path; frozen
    # 3/0: §136's market read — refresh button, the shell's instrument switch, DOMContentLoaded.
    "market-read.js": (3, 0),
    "navreturn.js": (2, 0),   # §119: the showView wrap's boot install + the chip's delegated click; page-lifetime by design
    # 4/0: §117's rebind capture — one more page-lifetime keydown listener in the menu, in the
    # capture phase and inert unless the user is choosing a combination (it must run before
    # the dispatcher, so it cannot live in the registry).
    "menu.js": (4, 0),   # boot-time listener(s) with no teardown path; frozen
    # 20/0: §119 removed the in-bar hide button's listener; the rest include the profile
    # store's own "something changed" subscription, so the Profiles group cannot drift from the view.
    "menubar.js": (21, 0),   # boot-time listeners, no teardown path; the §134 fix swapped the
                             # scroll-event closer (1 out) for two REAL gesture closers — wheel and
                             # touchmove (2 in) — because the suite's panels scroll themselves and a
                             # scroll event is not proof of a user gesture; frozen
    "news.js": (3, 0),   # boot-time listener(s) with no teardown path; frozen
    "ofx-view.js": (32, 0),   # boot-time listener(s) with no teardown path; frozen
    "ofx.js": (9, 1),   # 9 adds vs 1 removes reachable today; frozen
    # 5/0: §136's option flow — refresh button, the feed select, the symbol box, the shell's own
    # instrument switch, and the DOMContentLoaded boot; page-lifetime, poller on the pause registry.
    "option-flow.js": (5, 0),
    "options.js": (6, 0),   # boot-time listener(s) with no teardown path; frozen
    "paper.js": (2, 0),   # boot-time listener(s) with no teardown path; frozen
    "pause.js": (2, 0),   # boot-time listener(s) with no teardown path; frozen
    "platforms.js": (17, 0),   # boot-time listener(s) with no teardown path; frozen
    "presets.js": (4, 0),   # the preset combobox's boot listeners (select change, input sync x2, DOMContentLoaded); frozen
    "profiles.js": (3, 0),   # boot-time listener(s) with no teardown path; frozen
    "tips.js": (1, 0),   # the Guide-mount observer's DOMContentLoaded; frozen
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
    "ui.js": (11, 0),   # 8 + the toast Help-> delegation + the boot source-list fill (2026-09-19)
                        # + the Data-menu source convergence (ofap:source re-seeds an open Settings
                        # form, whose Save would otherwise roll the switch back); frozen
    # 5/0: §136's volatility surface — refresh button, chain-source select, symbol box, the shell's
    # own instrument switch, and the DOMContentLoaded boot; page-lifetime, poller on the pause
    # registry (an option chain is not a tick chart: 20 s, and P holds it like everything else).
    "volatility.js": (5, 0),
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
