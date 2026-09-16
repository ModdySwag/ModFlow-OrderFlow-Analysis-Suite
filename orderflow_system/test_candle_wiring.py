"""The candle-close wiring assertion must catch MIS-ROUTING, not just absence (Tier 2.1 pin).

``_on_candle_close`` (the analytics pass) and ``_on_candle_closed`` (persistence + WS
broadcast) differ by one letter; the historical bug class is a future edit wiring the wrong
one — candles persisted twice or analytics run twice. ``_verify_candle_wiring`` now checks
identity (the analytics callback must sit on the pipeline's own candle builder; the
persistence wire must point at the orchestrator's own ``_on_candle_closed``), so this test
drives the good wiring and both mis-wire shapes.
"""

from __future__ import annotations

import logging

from orderflow_system.config.settings import get_btcusd_config
from orderflow_system.desktop.engine import _verify_candle_wiring

LOG = "orderflow_system.desktop.engine"


def _system():
    from orderflow_system.main import OrderflowSystem
    return OrderflowSystem(instruments=[get_btcusd_config()])


def _errors(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]


def test_good_wiring_logs_no_error(caplog):
    system = _system()
    with caplog.at_level(logging.INFO, logger=LOG):
        _verify_candle_wiring(system)
    assert _errors(caplog) == []
    assert any("wired in-orchestrator" in r.getMessage() for r in caplog.records)


def test_persistence_wire_pointed_at_the_analytics_pass_is_reported(caplog):
    system = _system()
    sym = next(iter(system.pipelines))
    # The exact drift this guards: the persistence wire aimed at the ANALYTICS method.
    system.pipelines[sym]._on_candle_closed_callback = system.pipelines[sym]._on_candle_close
    with caplog.at_level(logging.ERROR, logger=LOG):
        _verify_candle_wiring(system)
    assert any("MIS-ROUTED" in m and sym in m for m in _errors(caplog)), _errors(caplog)


def test_missing_persistence_wire_is_reported(caplog):
    system = _system()
    sym = next(iter(system.pipelines))
    system.pipelines[sym]._on_candle_closed_callback = None
    with caplog.at_level(logging.ERROR, logger=LOG):
        _verify_candle_wiring(system)
    assert any("NOT wired" in m and sym in m for m in _errors(caplog)), _errors(caplog)


def test_analytics_callback_drift_is_reported(caplog):
    system = _system()
    sym = next(iter(system.pipelines))
    system.pipelines[sym].candle_builder.on_candle_close = None   # the wrapper-compensation smell
    with caplog.at_level(logging.ERROR, logger=LOG):
        _verify_candle_wiring(system)
    assert any("MIS-ROUTED" in m and sym in m for m in _errors(caplog)), _errors(caplog)
