"""The desktop engine must run the cooldown/score from the user's `risk` config (Tier 1.2 pin).

The v0.1b audit read the hardcoded 30 s in ``OrderflowSystem.__init__`` and concluded the
config knob was dead. It is not dead for the app — ``EngineController.start()`` overrides both
values from the config `risk` block right after construction — but nothing pinned that
override, so the knob could silently stop working. This is the pin, end to end through the
controller's own start path (heavy collaborators stubbed; no feeds, no settings mutation).
"""

from __future__ import annotations

import asyncio

from orderflow_system.config.settings import get_nas100_config
from orderflow_system.desktop import engine as engine_mod


def _start_with(monkeypatch, cfg):
    monkeypatch.setattr(engine_mod, "select_instruments", lambda c: ([get_nas100_config()], []))
    monkeypatch.setattr(engine_mod, "apply_settings", lambda c: None)

    async def _no_atlas(system, c):
        return None

    async def _no_run(self, system):
        return None

    monkeypatch.setattr(engine_mod, "_wire_atlas", _no_atlas)
    monkeypatch.setattr(engine_mod.EngineController, "_run", _no_run)

    async def scenario():
        ctrl = engine_mod.EngineController()
        result = await ctrl.start(cfg)
        return ctrl, result

    return asyncio.run(scenario())


def test_risk_block_values_govern_the_aggregator(monkeypatch):
    ctrl, result = _start_with(monkeypatch, {
        "data_source": "bybit",
        "risk": {"signal_cooldown_seconds": 123.0, "min_composite_score": 77.0},
    })
    assert result["ok"] is True, result
    agg = ctrl.system.aggregator
    assert agg.signal_cooldown_seconds == 123.0, "the config cooldown must reach the aggregator"
    assert agg.min_composite_score == 77.0


def test_missing_risk_block_falls_back_to_the_documented_defaults(monkeypatch):
    ctrl, result = _start_with(monkeypatch, {"data_source": "bybit", "risk": {}})
    assert result["ok"] is True, result
    agg = ctrl.system.aggregator
    assert agg.signal_cooldown_seconds == 30.0     # config_store risk default
    assert agg.min_composite_score == 40.0
