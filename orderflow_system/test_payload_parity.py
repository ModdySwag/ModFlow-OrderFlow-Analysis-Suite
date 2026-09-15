"""Payload parity: live payloads must keep the demo payload shapes.

Audit P1's failure mode was "an endpoint is completed for live but the JS reads
demo keys". This module pins the contract: every key the demo generator emits
must exist in the live payload for the same endpoint (extra live keys are fine).

If a shape changes deliberately, change it in `dashboard/demo_data.py` AND here.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from orderflow_system.analytics.footprint import FootprintBar
from orderflow_system.dashboard import demo_data
from orderflow_system.dashboard.app import (
    _live_footprint_bars,
    _live_microstructure,
    _live_tape_rows,
)
from orderflow_system.data.models import Candle, FootprintLevel, Side, Signal, SignalType, Tick

SYMBOL = "BTCUSDT"


def _missing(demo_obj, live_obj) -> set:
    """Keys present in the demo payload but absent from the live payload."""
    return set(demo_obj) - set(live_obj)


def test_tape_rows_match_demo_keys():
    demo_row = demo_data.demo_tape_trades(SYMBOL, count=1)[0]

    rows = _live_tape_rows([Tick(timestamp_ms=1_700_000_000_000, price=20_000.0, size=2.0, side=Side.BUY)])

    assert len(rows) == 1
    assert _missing(demo_row, rows[0]) == set()
    assert rows[0]["side"] == "buy"
    assert rows[0]["time"] == 1_700_000_000.0


def test_footprint_bars_match_demo_keys():
    demo_bar = demo_data.demo_footprint(SYMBOL)[0]
    demo_level = demo_bar["levels"][0]

    bar = FootprintBar(
        timestamp_ms=1_700_000_000_000,
        open=20_000.0, high=20_010.0, low=19_990.0, close=20_005.0,
        levels={
            19_990.0: FootprintLevel(price=19_990.0, bid_volume=4, ask_volume=1),
            20_000.0: FootprintLevel(price=20_000.0, bid_volume=2, ask_volume=9),
            20_010.0: FootprintLevel(price=20_010.0, bid_volume=1, ask_volume=1),
        },
    )
    pipeline = SimpleNamespace(footprint_engine=SimpleNamespace(history=[bar]))

    bars = _live_footprint_bars(pipeline)

    assert len(bars) == 1
    assert _missing(demo_bar, bars[0]) == set()
    assert _missing(demo_level, bars[0]["levels"][0]) == set()
    # levels are ordered by price and the POC is the heaviest level
    assert [lv["price"] for lv in bars[0]["levels"]] == [19_990.0, 20_000.0, 20_010.0]
    assert bars[0]["poc"] == 20_000.0


def _stub_system_and_pipeline():
    candle = Candle(
        timestamp_ms=1_700_000_000_000, open=20_000.0, high=20_010.0,
        low=19_990.0, close=20_005.0, volume=50.0, buy_volume=30.0, sell_volume=20.0,
    )
    signals = [
        Signal(timestamp_ms=candle.timestamp_ms, signal_type=SignalType.ABSORPTION,
               direction=Side.BUY, price_level=19_995.0, strength=70.0, details={"attempts": 2}),
        Signal(timestamp_ms=candle.timestamp_ms, signal_type=SignalType.DIVERGENCE,
               direction=Side.SELL, price_level=20_005.0, strength=55.0, details={}),
    ]
    pipeline = SimpleNamespace(
        symbol=SYMBOL,
        candle_builder=SimpleNamespace(get_recent_candles=lambda n: [candle] * 5),
        delta_engine=SimpleNamespace(cumulative_delta=123.0),
        config=SimpleNamespace(volume_profile=SimpleNamespace(session="NY_CASH")),
    )
    system = SimpleNamespace(recent_signals=lambda symbol, count: signals)
    return system, pipeline


def test_microstructure_matches_demo_keys():
    demo = demo_data.demo_microstructure(SYMBOL)
    system, pipeline = _stub_system_and_pipeline()

    live = _live_microstructure(system, pipeline)

    assert _missing(demo, live) == set()
    assert live["source"] == "engine"
    assert live["absorption"]["attempts"] == 2
    assert live["absorption"]["side"] == "buy"
    assert live["initiative"]["direction"] == "none"
    assert live["delta"]["divergence"] is True
    assert {p["type"] for p in live["patterns"]} == {"absorption", "delta_divergence"}


# ── Alpaca equity symbols (plan T28) ────────────────────────────────────

@pytest.mark.parametrize("symbol", ["AAPL", "SPY", "QQQ", "MSFT"])
def test_alpaca_symbols_serve_the_same_shapes(symbol):
    """Every symbol the Alpaca view offers must be servable with no keys linked —
    otherwise the UI looks broken on the exact instruments Alpaca is sold for."""
    demo_row = demo_data.demo_tape_trades(symbol, count=1)[0]
    rows = _live_tape_rows([Tick(timestamp_ms=1_700_000_000_000, price=232.0, size=10.0, side=Side.SELL)])
    assert _missing(demo_row, rows[0]) == set()

    demo_bar = demo_data.demo_footprint(symbol)[0]
    bar = FootprintBar(timestamp_ms=1_700_000_000_000, open=231.0, high=233.0, low=230.5, close=232.4,
                       levels={231.0: FootprintLevel(price=231.0, bid_volume=3, ask_volume=1),
                               232.0: FootprintLevel(price=232.0, bid_volume=1, ask_volume=4)})
    live_bars = _live_footprint_bars(SimpleNamespace(footprint_engine=SimpleNamespace(history=[bar])))
    assert _missing(demo_bar, live_bars[0]) == set()
    assert _missing(demo_bar["levels"][0], live_bars[0]["levels"][0]) == set()

    system = SimpleNamespace(recent_signals=lambda s, n: [])
    demo_micro = demo_data.demo_microstructure(symbol)
    live_micro = _live_microstructure(system, _stub_system_and_pipeline()[1])
    assert _missing(demo_micro, live_micro) == set()


def test_alpaca_symbols_have_plausible_demo_prices():
    """The equity base prices must look like equities, not the 1000.0 fallback."""
    for symbol, low, high in (("AAPL", 150, 400), ("SPY", 400, 800), ("QQQ", 350, 700)):
        row = demo_data.demo_tape_trades(symbol, count=1)[0]
        assert low < row["price"] < high, f"{symbol} demo price {row['price']} is not plausible"
