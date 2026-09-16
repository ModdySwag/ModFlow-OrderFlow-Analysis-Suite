"""A Bybit trade without the venue's own T stamp warns once and never lies silently (Tier 2.5).

The fallback itself (local wall clock) is the pre-existing behaviour and stays — timestamps
must still be usable for ordering. What is new: the substitution is announced exactly once
per connection, so a feed gap can no longer produce quietly-wrong session timestamps.
"""

from __future__ import annotations

import asyncio
import logging
import time

from orderflow_system.data.bybit_feed import BybitFeed


def _feed():
    seen = []

    async def on_tick(symbol, tick):
        seen.append(tick)

    return BybitFeed(["BTCUSDT"], on_tick=on_tick), seen


def test_t_missing_falls_back_to_local_clock_with_one_warning(caplog):
    feed, seen = _feed()
    msg = {"topic": "publicTrade.BTCUSDT", "data": [
        {"S": "Buy", "p": "98000", "v": "1.5", "i": "t1"},          # no T
        {"S": "Sell", "p": "98001", "v": "0.5", "i": "t2"},         # still no T
    ]}
    before = int(time.time() * 1000)
    with caplog.at_level(logging.WARNING, logger="orderflow_system.data.bybit_feed"):
        asyncio.run(feed._handle_trades(msg))
    after = int(time.time() * 1000)

    assert len(seen) == 2
    assert all(before <= t.timestamp_ms <= after for t in seen), [t.timestamp_ms for t in seen]
    warnings = [r for r in caplog.records if "without T" in r.getMessage()]
    assert len(warnings) == 1, "the fallback must be announced exactly once, not per trade"
    assert feed._ts_fallback_warned is True


def test_t_present_is_used_verbatim_and_does_not_warn(caplog):
    feed, seen = _feed()
    msg = {"topic": "publicTrade.BTCUSDT", "data": [
        {"S": "Buy", "p": "98000", "v": "1.0", "i": "t3", "T": 1_700_000_000_123}]}
    with caplog.at_level(logging.WARNING, logger="orderflow_system.data.bybit_feed"):
        asyncio.run(feed._handle_trades(msg))
    assert seen[0].timestamp_ms == 1_700_000_000_123
    assert feed._ts_fallback_warned is False
    assert [r for r in caplog.records if "without T" in r.getMessage()] == []


def test_the_latch_starts_clear_on_a_fresh_feed():
    feed, _ = _feed()
    assert feed._ts_fallback_warned is False
