"""Pattern detectors — absorption, divergence, exhaustion, initiative and sweeps."""
from __future__ import annotations

from typing import Any

#: Detector signal histories are diagnostic ring buffers, not archives: /api/markers re-serialises
#: them on every poll, so an unbounded list grew for the whole session (audit A-04).
SIGNAL_HISTORY_MAX = 500


def remember_signal(history: list, signal: Any) -> None:
    """Append to a signal history and keep the buffer bounded."""
    history.append(signal)
    if len(history) > SIGNAL_HISTORY_MAX:
        del history[:-SIGNAL_HISTORY_MAX]
