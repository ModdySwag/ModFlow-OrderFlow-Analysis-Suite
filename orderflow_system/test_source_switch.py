"""The data-source switch must actually ask the engine to restart (regression pin).

`EngineController.state` is a **property**, so `engine.state()` raised
`TypeError: 'str' object is not callable`. The endpoint's `except` swallowed it and reported
"the restart failed (…)" while the source had in fact been saved — so picking a source in the
menu never restarted the engine and showed an error note. These tests pin the call shape:
before the fix, the first test fails with "the engine was never asked to restart".
"""

from __future__ import annotations

import asyncio

from orderflow_system.desktop import api


def _fake_engine(state: str, calls: list):
    class FakeEngine:
        """Mirrors the real controller: `state` is a value, not a callable."""

        def __init__(self) -> None:
            self.state = state

        async def restart(self, cfg):
            calls.append(cfg)
            return {"ok": True, "state": "running"}

    return FakeEngine()


def _stub_config(monkeypatch):
    saved = {}
    monkeypatch.setattr(api.config_store, "load_config", lambda: {"data_source": "bybit"})

    def _save(cfg):
        saved.update(cfg)
        return dict(cfg)

    monkeypatch.setattr(api.config_store, "save_config", _save)
    return saved


def test_source_switch_restarts_a_running_engine(monkeypatch):
    saved = _stub_config(monkeypatch)
    calls = []
    monkeypatch.setattr(api.engine_mod, "engine", _fake_engine("running", calls))

    result = asyncio.run(api.set_source({"source": "bybit"}))

    assert result["ok"] is True, result
    assert saved.get("data_source") == "bybit"
    assert calls, "the engine was never asked to restart"
    assert result["note"] == "engine restarted on the new source", result


def test_source_switch_leaves_a_stopped_engine_alone(monkeypatch):
    _stub_config(monkeypatch)
    calls = []
    monkeypatch.setattr(api.engine_mod, "engine", _fake_engine("stopped", calls))

    result = asyncio.run(api.set_source({"source": "bybit"}))

    assert result["ok"] is True, result
    assert not calls, "a stopped engine must not be restarted by a source switch"
    assert result["note"] == "source saved; press Start engine to stream it", result


def test_source_switch_rejects_an_unknown_source():
    result = asyncio.run(api.set_source({"source": "definitely-not-a-source"}))

    assert result["ok"] is False
    assert "unknown source" in result["error"]
