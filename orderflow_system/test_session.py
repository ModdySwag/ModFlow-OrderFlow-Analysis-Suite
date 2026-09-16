"""P3-2 (R4): the session window is one function, and the VP stops mixing sessions.

Gates from the plan: unit tests on the session-window function + a VP comparison across a
simulated boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone

from orderflow_system.analytics.session import session_window
from orderflow_system.analytics.volume_profile import VolumeProfileConfig, VolumeProfileEngine
from orderflow_system.data.models import Candle, FootprintLevel


def _ms(y, mo, d, h, mi):
    return int(datetime(y, mo, d, h, mi, tzinfo=timezone.utc).timestamp() * 1000)


def test_session_window_utc_midnight_default():
    start, end, label = session_window(_ms(2026, 1, 2, 0, 30), 0)
    assert label == "2026-01-02"
    assert start == _ms(2026, 1, 2, 0, 0)
    assert end == _ms(2026, 1, 3, 0, 0)


def test_session_window_before_the_boundary_belongs_to_yesterday():
    start, _end, label = session_window(_ms(2026, 1, 1, 23, 30), 0)
    assert label == "2026-01-01"
    assert start == _ms(2026, 1, 1, 0, 0)


def test_session_window_honours_the_configured_hour():
    start, _end, label = session_window(_ms(2026, 1, 2, 5, 0), 6)
    assert label == "2026-01-01" and start == _ms(2026, 1, 1, 6, 0)
    start2, _e2, label2 = session_window(_ms(2026, 1, 2, 6, 0), 6)   # the boundary is inclusive
    assert label2 == "2026-01-02" and start2 == _ms(2026, 1, 2, 6, 0)


def test_session_window_junk_hour_falls_back():
    for junk in (99, -1, None, "6", True):
        start, _end, label = session_window(_ms(2026, 1, 2, 0, 30), junk)
        assert label == "2026-01-02", junk


def _candle(ts_ms, price, volume):
    return Candle(
        timestamp_ms=ts_ms, open=price, high=price + 0.2, low=price - 0.2, close=price + 0.1,
        volume=volume, buy_volume=volume * 0.6, sell_volume=volume * 0.4,
        footprint={price: FootprintLevel(price, bid_volume=volume * 0.6, ask_volume=volume * 0.4)},
    )


def test_vp_comparison_across_a_simulated_boundary():
    """The old code fetched a rolling 24 h and called it "today": at 00:30 the previous
    session's volume still moved the POC. The configured window excludes it."""
    engine = VolumeProfileEngine(VolumeProfileConfig())
    prev = [_candle(_ms(2026, 1, 1, 23, m), 100.0, 50) for m in (0, 30)]     # yesterday's session
    cur = [_candle(_ms(2026, 1, 2, 0, m), 110.0, 20) for m in (0, 15)]       # the new session
    now = _ms(2026, 1, 2, 0, 30)

    start, _end, label = session_window(now, 0)
    windowed = [c for c in prev + cur if start <= c.timestamp_ms <= now]

    vp_windowed = engine.compute_from_candles(windowed, session_date=label)
    vp_mixed = engine.compute_from_candles(prev + cur, session_date="2026-01-02")

    assert len(windowed) == len(cur)                     # yesterday's candles are OUT
    assert abs(vp_windowed.poc - 110.0) < 1e-6           # only the new session's price
    assert abs(vp_mixed.poc - 100.0) < 1e-6              # the mixing the item names, demonstrated
    assert vp_windowed.session_date == "2026-01-02"
