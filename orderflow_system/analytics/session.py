"""Session windows — one boundary, one label, computed identically everywhere.

R4 (sweep §4): `session_date` used to be UTC-today over a rolling 24 h of candles, so at the
UTC boundary "today's" value area mixed two sessions. The boundary is now a config value
(`data.session_start_hour`, UTC, default 0) and this module is the one place it is read.

Pure functions only: `main.py` calls them with a clock, tests call them with any clock.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def session_window(now_ms: int, start_hour: int = 0) -> tuple[int, int, str]:
    """The session containing `now_ms`, as (start_ms, end_ms, label) — all UTC.

    The boundary is `start_hour` on the most recent day at or before now; `end_ms` is the
    start of the NEXT session (exclusive upper bound). `label` is the session's start date
    (`YYYY-MM-DD`) — the same string shape `session_date` always carried, so stored
    profiles stay comparable. A junk hour falls back to 0 (the documented default) rather
    than raising: this reads config, and config must never crash the profile loop.
    """
    hour = start_hour if isinstance(start_hour, int) and not isinstance(start_hour, bool)         and 0 <= start_hour <= 23 else 0
    now = datetime.fromtimestamp(now_ms / 1000.0, tz=timezone.utc)
    boundary = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if boundary > now:
        boundary -= timedelta(days=1)
    nxt = boundary + timedelta(days=1)
    return int(boundary.timestamp() * 1000), int(nxt.timestamp() * 1000), boundary.strftime("%Y-%m-%d")
