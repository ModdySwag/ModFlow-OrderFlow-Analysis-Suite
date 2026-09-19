"""The sweep window is cut against feed time, not the host clock (audit C-02).

A venue (or a replay) whose stamps trail the host clock used to make ``count_swept_levels()``
return 0 while consumptions sat in the tracker's history — a detector that looks alive and
never fires. The window now moves with the newest snapshot's own stamp.
"""
from __future__ import annotations

import time

from orderflow_system.analytics.orderbook import OrderbookTracker
from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot

#: An hour behind the host clock — far larger than any real venue skew, so this pins the class
#: of defect rather than one venue's drift.
FEED_NOW_MS = int(time.time() * 1000) - 3_600_000


def _snapshot(ts_ms: int, ask_qty: float) -> OrderbookSnapshot:
    asks = [OrderbookLevel(price=100.0 + i, quantity=ask_qty + i) for i in range(5)]
    bids = [OrderbookLevel(price=99.0 - i, quantity=50.0 + i) for i in range(5)]
    return OrderbookSnapshot(timestamp_ms=ts_ms, bids=bids, asks=asks)


def test_swept_levels_count_with_feed_stamps_behind_the_host_clock():
    tracker = OrderbookTracker()
    tracker.update(_snapshot(FEED_NOW_MS - 1000, ask_qty=40.0))
    tracker.update(_snapshot(FEED_NOW_MS, ask_qty=1.0))          # three+ ask levels eaten

    assert tracker.count_swept_levels(time_window_ms=3000, side="ask") >= 3
    assert tracker.total_consumed_volume(time_window_ms=3000, side="ask") > 0.0


def test_the_window_still_excludes_old_consumptions():
    tracker = OrderbookTracker()
    tracker.update(_snapshot(FEED_NOW_MS - 60_000, ask_qty=40.0))
    tracker.update(_snapshot(FEED_NOW_MS - 59_000, ask_qty=1.0))  # consumed a minute earlier
    tracker.update(_snapshot(FEED_NOW_MS, ask_qty=1.0))           # newest stamp moves the window on

    assert tracker.count_swept_levels(time_window_ms=3000, side="ask") == 0
