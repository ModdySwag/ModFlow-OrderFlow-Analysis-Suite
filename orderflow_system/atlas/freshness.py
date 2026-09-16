"""One reading of "how old is this sample" — the age policy every layer shares.

The policy was born in ``crossvenue.py`` (the cross-venue top of book), because that is where the
first real ages were needed. P1-10 hoisted it here so the engine status, the live chip and the UI
chips all read the SAME windows instead of inventing their own:

* depth **5 s** — a depth feed updates continuously, so seconds of silence is stale;
* quote **60 s** — a quote feed does not (Alpaca's crypto quotes tick a few times a minute;
  calling that "stale" would throw away a perfectly usable top of book — measured: 13.7 s);
* trades **5 s** — the tape is continuous, like depth;
* candles **60 s** — one closed candle a minute is the normal cadence.

``assess()`` is the one assessment: an age, whether the age is even KNOWN, the window it was
judged against, and the verdict. A sample with ``last_ms == 0`` means the clock is unknown
(a venue clock, an update id — see ``clock.py``) and is reported as ``age_known: False`` with
``stale: False``: an unknown age is reported as unknown, never invented, never called stale.

The UI mirrors these windows in ``desktop/ui/freshness.js`` and ``test_freshness.py`` pins the
two tables equal, so a change here cannot drift past the browser.
"""

from __future__ import annotations

import time
from typing import Any, Optional

STALE_DEPTH_MS = 5_000
STALE_QUOTE_MS = 60_000
STALE_TRADES_MS = 5_000
STALE_CANDLE_MS = 60_000

#: Every kind the app assesses, in one table.
WINDOWS_MS = {
    "depth": STALE_DEPTH_MS,
    "quote": STALE_QUOTE_MS,
    "trades": STALE_TRADES_MS,
    "candles": STALE_CANDLE_MS,
}

#: The fallback for a kind nobody declared: treat it like a continuous feed.
DEFAULT_WINDOW_MS = STALE_DEPTH_MS


def window_ms(kind: str) -> int:
    """How long a sample of this kind may go without an update before it is called stale."""
    return WINDOWS_MS.get(str(kind or ""), DEFAULT_WINDOW_MS)


def assess(kind: str, last_ms: Any, now_ms: Optional[int] = None,
           window: Optional[int] = None) -> dict[str, Any]:
    """The age of one sample, the window it is judged against, and the verdict.

    ``last_ms == 0``/``None`` → ``age_known: False`` (the clock is unknown; nothing is invented).
    ``window`` overrides the kind's policy (used by crossvenue's explicit ``stale_ms`` query).
    """
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    try:
        last = int(last_ms or 0)
    except (TypeError, ValueError):
        last = 0
    span = int(window) if window is not None else window_ms(kind)
    age = max(0, now - last) if last else 0
    return {
        "age_ms": age,
        "age_known": bool(last),
        "window_ms": span,
        "stale": bool(last) and age > span,
    }
