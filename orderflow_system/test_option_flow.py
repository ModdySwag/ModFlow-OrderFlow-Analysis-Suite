
"""
Tests for the option flow classification engine — pure functions, no network.
"""

from __future__ import annotations


from orderflow_system.atlas.option_flow import (
    OptionTrade,
    classify_trade,
    detect_sweeps,
    classify_stream,
    BLOCK_SIZE_MIN,
)


# ── helpers ──────────────────────────────────────────────────────────────────────

def _trade(symbol="BTCUSDT", expiry="16SEP26", strike=65000.0, side="call",
           size=10.0, price=0.50, timestamp_ms=1700000000000, **kwargs):
    return OptionTrade(symbol=symbol, expiry=expiry, strike=strike, side=side,
                       size=size, price=price, timestamp_ms=timestamp_ms, **kwargs)


# ── classify_trade ───────────────────────────────────────────────────────────────

class TestClassifyTrade:
    def test_routine_small_print(self):
        t = _trade(size=10.0, price=0.50)
        c = classify_trade(t)
        assert c.classification == "routine"
        assert "routine print" in c.reason

    def test_block_large_print(self):
        t = _trade(size=100.0, price=0.50)
        c = classify_trade(t)
        assert c.classification == "block"
        assert "large single-print block" in c.reason

    def test_block_at_threshold(self):
        t = _trade(size=BLOCK_SIZE_MIN, price=0.50)
        c = classify_trade(t)
        assert c.classification == "block"

    def test_block_below_threshold(self):
        t = _trade(size=BLOCK_SIZE_MIN - 1, price=0.50)
        c = classify_trade(t)
        assert c.classification == "routine"

    def test_unusual_premium_high_ratio(self):
        t = _trade(size=50.0, price=2.0, oi_at_trade=800.0)
        c = classify_trade(t)
        assert c.classification == "unusual_premium"
        assert "abnormally high premium" in c.reason

    def test_not_unusual_at_low_ratio(self):
        t = _trade(size=50.0, price=0.5, oi_at_trade=800.0)
        c = classify_trade(t)
        # Low premium ratio → not unusual; but size at block threshold → block.
        assert c.classification == "block"

    def test_unusual_premium_requires_oi(self):
        t = _trade(size=100.0, price=5.0, oi_at_trade=None)
        c = classify_trade(t)
        # No OI → can't compute ratio → falls to block (size >= BLOCK_SIZE_MIN)
        assert c.classification == "block"

    def test_nan_size_is_routine(self):
        t = _trade(size=float("nan"), price=0.50)
        c = classify_trade(t)
        assert c.classification == "routine"

    def test_malformed_trade(self):
        c = classify_trade(_trade(size=None, price=None))
        assert c.classification == "routine"


# ── detect_sweeps ────────────────────────────────────────────────────────────────

class TestDetectSweeps:
    def test_no_sweep_single_strike(self):
        trades = [
            _trade(strike=65000.0, size=100.0, timestamp_ms=1700000000000),
            _trade(strike=65000.0, size=150.0, timestamp_ms=1700000000100),
        ]
        sweeps = detect_sweeps(trades)
        assert len(sweeps) == 0

    def test_no_sweep_few_trades(self):
        trades = [
            _trade(strike=65000.0, size=100.0, timestamp_ms=1700000000000),
            _trade(strike=66000.0, size=100.0, timestamp_ms=1700000000100),
        ]
        sweeps = detect_sweeps(trades)
        assert len(sweeps) == 0  # only 2 strikes, need SWEEP_MIN_STRIKES (3)

    def test_sweep_across_strikes(self):
        trades = [
            _trade(strike=64000.0, size=100.0, timestamp_ms=1700000000000),
            _trade(strike=65000.0, size=100.0, timestamp_ms=1700000000100),
            _trade(strike=66000.0, size=100.0, timestamp_ms=1700000000200),
            _trade(strike=67000.0, size=100.0, timestamp_ms=1700000000300),
        ]
        sweeps = detect_sweeps(trades)
        assert len(sweeps) == 1
        assert len(sweeps[0].strikes) == 4
        assert sweeps[0].total_size == 400.0

    def test_unusual_premium_requires_oi(self):
        t = _trade(size=100.0, price=5.0, oi_at_trade=None)
        c = classify_trade(t)
        # No OI → can't compute ratio → falls to block (size >= BLOCK_SIZE_MIN)
        assert c.classification == "block"

    def test_nan_size_is_routine(self):
        t = _trade(size=float("nan"), price=0.50)
        c = classify_trade(t)
        assert c.classification == "routine"

    def test_sweep_within_window(self):
        trades = [
            _trade(strike=64000.0, size=100.0, timestamp_ms=1700000000000),
            _trade(strike=65000.0, size=100.0, timestamp_ms=1700000000100),
            _trade(strike=66000.0, size=100.0, timestamp_ms=1700000000200),
            _trade(strike=67000.0, size=100.0, timestamp_ms=1700010000000),  # outside window
        ]
        sweeps = detect_sweeps(trades)
        # First 3 are within window; 4th is outside.
        assert len(sweeps) >= 1

    def test_no_sweep_below_total_size(self):
        trades = [
            _trade(strike=64000.0, size=10.0, timestamp_ms=1700000000000),
            _trade(strike=65000.0, size=10.0, timestamp_ms=1700000000100),
            _trade(strike=66000.0, size=10.0, timestamp_ms=1700000000200),
        ]
        sweeps = detect_sweeps(trades)
        assert len(sweeps) == 0  # total size 30 < SWEEP_MIN_TOTAL_SIZE (200)

    def test_empty_stream(self):
        assert detect_sweeps([]) == []

    def test_malformed_entries_skipped(self):
        trades = [
            _trade(strike=65000.0, size=100.0, timestamp_ms=1700000000000),
            "not a dict",
            None,
            42,
        ]
        sweeps = detect_sweeps(trades)
        # Only 1 valid trade → no sweep.
        assert len(sweeps) == 0


# ── classify_stream ──────────────────────────────────────────────────────────────

class TestClassifyStream:
    def test_empty_stream(self):
        r = classify_stream([])
        assert r.total_trades == 0
        assert r.n_sweeps == 0
        assert r.n_blocks == 0
        assert r.n_unusual == 0
        assert r.n_routine == 0

    def test_mixed_stream(self):
        trades = [
            _trade(strike=64000.0, size=5.0, price=0.10, timestamp_ms=1700000000000),
            _trade(strike=65000.0, size=100.0, price=0.50, timestamp_ms=1700000000100),
            _trade(strike=66000.0, size=50.0, price=2.0, oi_at_trade=800.0,
                   timestamp_ms=1700000000200),  # unusual premium
            _trade(strike=67000.0, size=8.0, price=0.20, timestamp_ms=1700000000300),
        ]
        r = classify_stream(trades)
        assert r.total_trades == 4
        assert r.n_blocks == 1  # the 100-contract print
        assert r.n_unusual == 1  # the high-premium print
        assert r.n_routine == 2  # the two small prints

    def test_sweep_in_stream(self):
        trades = [
            _trade(strike=64000.0, size=100.0, timestamp_ms=1700000000000),
            _trade(strike=65000.0, size=100.0, timestamp_ms=1700000000100),
            _trade(strike=66000.0, size=100.0, timestamp_ms=1700000000200),
        ]
        r = classify_stream(trades)
        assert r.n_sweeps == 1
        assert r.sweeps[0].total_size == 300.0

    def test_oi_lookup_used(self):
        trades = [
            _trade(strike=65000.0, size=50.0, price=2.0, timestamp_ms=1700000000000),
        ]
        oi_lookup = {"BTCUSDT|16SEP26|65000.0|call": 800.0}
        r = classify_stream(trades, oi_lookup=oi_lookup)
        assert r.n_unusual == 1

    def test_symbol_consistency(self):
        trades = [
            _trade(symbol="BTCUSDT", strike=65000.0, size=10.0, timestamp_ms=1700000000000),
            _trade(symbol="BTCUSDT", strike=66000.0, size=10.0, timestamp_ms=1700000000100),
        ]
        r = classify_stream(trades)
        assert r.symbol == "BTCUSDT"
