"""Every UI setInterval is either pause/hidden-guarded or on the frozen allow-list (G-09).

The audit found 22 of 40 timer sites registering with nothing, and the `pause.js` registry is
opt-in by design. This is the source-level classifier promoted from that coverage ledger: a timer
must carry one of the documented guard markers nearby, or its module must be listed in
SELF_GUARDED with a reason. The per-module counts are frozen too, so a new unguarded timer fails
even when a module is already excused.
"""

from __future__ import annotations

import re
from pathlib import Path

UI = Path(__file__).parent / "desktop" / "ui"

#: Markers that make a timer honest: the pause registry, the hidden check, the pause flag, or an
#: explicit clearInterval (self-managing loops that stop themselves).
GUARDS = ("OFAPPause.register", "document.hidden", "OFAP_PAUSED", "clearInterval")

#: Modules whose timers the v0.1b audit's coverage ledger classified as unguarded, frozen here
#: with the reason so the set can only shrink. Each entry means: known, counted, and NOT claimed
#: to be guarded — a new timer in the module still fails until it carries a guard marker.
SELF_GUARDED = {
    "alpaca-card.js": "ledger: poller without a pause/hidden guard (G-09 list)",
    "bus.js": "ledger: the channel sweep runs on its own cadence by design",
    "freshness.js": "ledger: 1 Hz chip repaint, no pause guard (G-09 list)",
    "fundamentals.js": "ledger: poll gated on its own intent check only",
    "guide.js": "ledger: boot retry loop, retires itself",
    "inbox.js": "ledger: poller without a pause/hidden guard (G-09 list)",
    "intent.js": "ledger: chip repaint loop (G-09 list)",
    "market-pressure.js": "ledger: poll checks its own intent only",
    "news.js": "ledger: poller without a pause/hidden guard (G-09 list)",
    "options.js": "ledger: poller without a pause/hidden guard (G-09 list)",
    "paper.js": "ledger: poller without a pause/hidden guard (G-09 list)",
    "profiles.js": "ledger: 30 s tick without a pause/hidden guard (G-09 list)",
    "search.js": "ledger: palette loops (G-09 list)",
    "steady.js": "ledger: activity loops by design (the module IS the guard)",
    "storage.js": "ledger: poller without a pause/hidden guard (G-09 list)",
    "ui.js": "ledger: shell boot loops (G-09 list)",
    "updates.js": "ledger: version poll, own visibilitychange check",
    "vwap.js": "ledger: poller without a pause/hidden guard (G-09 list)",
    "watchlist.js": "ledger: poller without a pause/hidden guard (G-09 list)",
}

#: Frozen per-module counts at the time of the v0.1b remediation: the number may only go DOWN.
FROZEN_COUNTS = {
    "alpaca-card.js": 2, "atlas-v2.js": 1, "bus.js": 1, "context.js": 1, "freshness.js": 1,
    "fundamentals.js": 1, "guide.js": 2, "inbox.js": 1, "intent.js": 1, "market-pressure.js": 1,
    "news.js": 1, "ofx-view.js": 3, "options.js": 1, "paper.js": 1, "pause.js": 1,
    "profiles.js": 1, "scanner.js": 1, "search.js": 3, "steady.js": 2, "storage.js": 1,
    "strips.js": 2, "ui.js": 4, "updates.js": 1, "vwap.js": 1, "watchlist.js": 1,
    "watermark.js": 2,
    # §136's four analytics panels: one cadence each, every one registered with OFAPPause.
    "gex.js": 1, "market-read.js": 1, "option-flow.js": 1, "volatility.js": 1,
}


def _sites(source: str) -> list[int]:
    return [m.start() for m in re.finditer(r"setInterval\s*\(", source)]


def test_every_timer_is_guarded_or_excused_with_a_reason():
    offenders: list[str] = []
    for path in sorted(UI.glob("*.js")):
        if path.name.endswith(".selftest.js"):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()
        for pos in _sites(source):
            line_no = source.count("\n", 0, pos)
            window = "\n".join(lines[max(0, line_no - 2):line_no + 10])
            if any(marker in window for marker in GUARDS):
                continue
            if path.name in SELF_GUARDED:
                continue
            offenders.append(f"{path.name}:{line_no + 1}")
    assert not offenders, ("unguarded setInterval site(s) — add a guard or an allow-list reason:\n"
                           + "\n".join(offenders))


def test_the_guard_surface_can_only_shrink():
    counts: dict[str, int] = {}
    for path in sorted(UI.glob("*.js")):
        if path.name.endswith(".selftest.js"):
            continue
        n = len(_sites(path.read_text(encoding="utf-8", errors="replace")))
        if n:
            counts[path.name] = n
    for name, frozen in FROZEN_COUNTS.items():
        assert counts.get(name, 0) <= frozen, f"{name}: {counts.get(name, 0)} timers > frozen {frozen}"
