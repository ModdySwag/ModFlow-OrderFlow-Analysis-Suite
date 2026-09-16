"""One reading of a venue timestamp, for every module that has to compare two clocks.

Bybit hands out three different things in a ``timestamp_ms`` field, and code that assumes one of
them breaks silently on the others:

* real epoch **milliseconds** (the trade feed),
* epoch **seconds** (the deeper ``orderbook.200`` feed),
* the book's **update id** (``u``) — an integer in the thousands that is not a clock at all.

Treating an update id as a clock collapsed the depth heatmap into ~50 columns per second; treating
one as a clock in the trade detector made every refilled level read as *"refilled -1789344734.5s
after being eaten"*, i.e. a latency of minus fifty-six years. Anything implausible as a 2020-or-later
epoch is replaced with the current time, so a comparison across the two feeds stays a duration
rather than a nonsense number.
"""

from __future__ import annotations

import time
from typing import Any, Optional

#: Before 2020-01-01 — nothing this app records predates it, so a smaller value is not a clock.
EPOCH_MS_FLOOR = 1_577_000_000_000

#: Anything under this is seconds rather than milliseconds (2286-11 is the last second before ms).
SECONDS_CEILING = 10_000_000_000


def as_epoch_ms(value: Any, fallback_ms: Optional[int] = None) -> int:
    """Normalise a venue timestamp to epoch milliseconds.

    ``fallback_ms`` lets a caller keep its own last known clock instead of the wall clock (a stream
    of snapshots stamped with sequence ids keeps a monotonic axis that way).
    """
    now = int(fallback_ms if fallback_ms is not None else time.time() * 1000)
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return now
    if ms <= 0:
        return now
    if ms < SECONDS_CEILING:             # seconds → ms
        ms *= 1000
    if ms < EPOCH_MS_FLOOR:              # still not a clock (an update id) → the caller's own clock
        return now
    return ms
