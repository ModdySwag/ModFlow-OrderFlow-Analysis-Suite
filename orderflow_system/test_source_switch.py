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


# ── the Binance source is wired (2026-09-16) ──────────────────────────────────────────────────
def test_the_binance_source_is_wired_and_switchable(monkeypatch):
    """`wired` is the whole switch: flipping it must make the source selectable end to end."""
    saved = _stub_config(monkeypatch)
    calls = []
    monkeypatch.setattr(api.engine_mod, "engine", _fake_engine("running", calls))

    result = asyncio.run(api.set_source({"source": "binance"}))

    assert result["ok"] is True, result
    assert saved.get("data_source") == "binance"
    assert calls, "the engine was never restarted onto Binance"


def test_the_hyperliquid_and_okx_sources_are_wired_and_switchable(monkeypatch):
    """`wired` is the whole switch: flipping it must make the source selectable end to end."""
    for source in ("hyperliquid", "okx"):
        saved = _stub_config(monkeypatch)
        calls = []
        monkeypatch.setattr(api.engine_mod, "engine", _fake_engine("running", calls))

        result = asyncio.run(api.set_source({"source": source}))

        assert result["ok"] is True, result
        assert saved.get("data_source") == source, result
        assert calls, f"the engine was never restarted onto {source}"


def test_an_unwired_source_still_refuses_with_the_honest_reason(monkeypatch):
    """Every shipped source is wired now — the refusal path stays pinned via the table itself."""
    monkeypatch.setattr(api, "FREE_SOURCES", api.FREE_SOURCES + (
        ("mexc", "MEXC", "reachable, no feed adapter in this build yet",
         "https://www.mexc.com/api/time", False),))

    result = asyncio.run(api.set_source({"source": "mexc"}))

    assert result["ok"] is False, result
    assert "no feed adapter" in result["error"], result


def test_datasources_advertises_binance_for_crypto_and_greys_the_rest(monkeypatch):
    cfg = {"data_source": "binance",
           "instruments": [{"symbol": "BTCUSDT"}, {"symbol": "NAS100"}]}
    monkeypatch.setattr(api.config_store, "load_config", lambda: cfg)
    monkeypatch.setattr(api.config_store, "instrument_cfg",
                        lambda c, sym: {"symbol": sym}, raising=False)
    monkeypatch.setattr(api.engine_mod, "mt5_status",
                        lambda: {"available": False, "reason": "not installed"})

    rows = asyncio.run(api.datasources())

    assert rows["binance"]["usable"] is True
    assert "BTCUSDT" in rows["binance"]["symbols"]
    assert "NAS100" not in rows["binance"]["symbols"], "an index is not a Binance perpetual"
    assert "BTCUSDT" in rows["bybit"]["symbols"], "the Bybit row must stay truthful too"


def test_the_binance_capable_rule_is_honest():
    from orderflow_system.desktop import engine as engine_mod

    assert engine_mod.binance_capable({"symbol": "BTCUSDT"}) is True
    assert engine_mod.binance_capable({"symbol": "ETHUSDT", "binance_symbol": "ETHUSDT"}) is True
    assert engine_mod.binance_capable({"symbol": "NAS100"}) is False
    assert engine_mod.binance_capable({"symbol": "XAUUSD"}) is False


def test_the_hyperliquid_and_okx_capable_rules_are_honest():
    from orderflow_system.desktop import engine as engine_mod

    for rule in (engine_mod.hyperliquid_capable, engine_mod.okx_capable):
        assert rule({"symbol": "BTCUSDT"}) is True
        assert rule({"symbol": "NAS100"}) is False
        assert rule({"symbol": "XAUUSD"}) is False
    assert engine_mod.hyperliquid_capable({"symbol": "KPEPEUSDT", "hyperliquid_symbol": "kPEPE"}) is True
    assert engine_mod.okx_capable({"symbol": "WIFUSDT", "okx_symbol": "WIF-USDT-SWAP"}) is True


def test_datasources_advertises_hyperliquid_and_okx_for_crypto(monkeypatch):
    cfg = {"data_source": "hyperliquid",
           "instruments": [{"symbol": "BTCUSDT"}, {"symbol": "NAS100"}]}
    monkeypatch.setattr(api.config_store, "load_config", lambda: cfg)
    monkeypatch.setattr(api.config_store, "instrument_cfg",
                        lambda c, sym: {"symbol": sym}, raising=False)
    monkeypatch.setattr(api.engine_mod, "mt5_status",
                        lambda: {"available": False, "reason": "not installed"})

    rows = asyncio.run(api.datasources())

    for source in ("hyperliquid", "okx"):
        assert rows[source]["usable"] is True
        assert "BTCUSDT" in rows[source]["symbols"]
        assert "NAS100" not in rows[source]["symbols"], "an index is not a crypto perpetual"


def test_the_config_allowlist_accepts_binance_and_falls_back_to_bybit():
    from orderflow_system.desktop.config_store import _sanitise

    for source in ("binance", "hyperliquid", "okx"):
        assert _sanitise({"data_source": source})["data_source"] == source

    fell_back = _sanitise({"data_source": "not-a-venue"})
    assert fell_back["data_source"] == "bybit"
