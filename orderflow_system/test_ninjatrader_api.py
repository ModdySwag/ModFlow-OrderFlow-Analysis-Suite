"""§84 — the NinjaTrader routes: the platform card payload, the plan and bridge saves, the live
probe against a mock bridge, the shipped-DLL state, and the instrument lane (front-month offers,
source-aware adds).

The routes are thin; the rules live in `desktop/platforms.py` (plans/workflow/bridge state),
`data/ninjatrader_feed.py` (the wire) and `engine.ninjatrader_*`. These pins cover the interface:
what the card carries, that saves clamp instead of trusting, that the probe talks to a real socket
(the mock speaks the shipped wire format), and that an add stamps the name the terminal resolved.
"""

from __future__ import annotations

import asyncio
import socket
import time

from orderflow_system.desktop import api, config_store, engine as engine_mod
from orderflow_system.test_ninjatrader_feed import MockNtBridge


def _cfg(*, source: str = "ninjatrader") -> dict:
    return {
        "data_source": source,
        "instruments": [
            {"symbol": "BTCUSDT", "asset_class": "Crypto", "enabled": True,
             "mt5_symbol": "", "bybit_symbol": "BTCUSDT", "alpaca_symbol": "",
             "ninjatrader_symbol": "", "tick_size": 0.5},
        ],
        "mt5": {},
        "ofx": {"symbol": ""},
        "platforms": {},
    }


def _stub(monkeypatch, cfg: dict) -> None:
    monkeypatch.setattr(config_store, "load_config", lambda: cfg)
    monkeypatch.setattr(config_store, "save_config", lambda c: c)
    monkeypatch.setattr(engine_mod.engine, "status",
                        lambda: {"running": False, "symbols": []})


def _free_port() -> int:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def _running_mock(**kwargs) -> MockNtBridge:
    server = MockNtBridge(**kwargs)
    server.start()
    for _ in range(200):
        if server.port:
            return server
        time.sleep(0.01)
    raise RuntimeError("mock bridge never bound")


# ── the platform card ─────────────────────────────────────────────────────────────────

def test_platforms_payload_carries_the_ninjatrader_rows(monkeypatch):
    _stub(monkeypatch, _cfg())
    out = asyncio.run(api.platforms_bridge())
    assert out["ok"] is True
    assert [p["id"] for p in out["ninjatrader_plans"]] == ["free", "monthly", "lifetime"]
    assert out["ninjatrader_plans"][0]["price"] == "0"
    assert out["ninjatrader_prices_as_of"]
    assert out["ninjatrader"]["host"] == "127.0.0.1"
    assert out["ninjatrader"]["port"] == 8790
    assert out["ninjatrader"]["protocol"] == "modflow-nt-jsonl"
    assert out["ninjatrader_workflow"]["steps"]
    assert out["ninjatrader_caveats"]
    assert any(link["id"] == "pricing" for link in out["ninjatrader_links"])
    # the bridge DLL ships with the app: the state block must always find it in-tree
    state = out["ninjatrader_bridge"]
    assert state["dll"]["exists"] is True
    assert len(state["dll"]["sha256"]) == 64
    assert state["note"]


def test_plan_save_stores_and_clamps(monkeypatch):
    cfg = _cfg()
    _stub(monkeypatch, cfg)
    out = asyncio.run(api.platforms_plan({"platform": "ninjatrader", "plan": "lifetime",
                                          "integrated": True}))
    assert out["ok"] is True
    assert out["platform"] == "ninjatrader"
    assert cfg["platforms"]["ninjatrader"]["plan"] == "lifetime"
    assert cfg["platforms"]["ninjatrader"]["integrated"] is True
    assert out["ninjatrader"]["plan"] == "lifetime"
    assert out["workflow"]["plan_kind"] == "integrated"   # the Lifetime plan's own kind

    clamped = asyncio.run(api.platforms_plan({"platform": "ninjatrader", "plan": "platinum"}))
    assert clamped["ninjatrader"]["plan"] == "free"
    assert clamped["workflow"]["plan_kind"] == "free"


def test_bridge_save_keeps_the_socket_honest(monkeypatch):
    cfg = _cfg()
    _stub(monkeypatch, cfg)
    out = asyncio.run(api.ninjatrader_settings_save(
        {"host": "127.0.0.1", "port": 70000, "symbol": "NQ", "enabled": True}))
    assert out["ninjatrader"]["port"] == 8790            # out-of-range port clamped
    assert out["ninjatrader"]["symbol"] == "NQ"
    assert out["ninjatrader"]["enabled"] is True
    assert "127.0.0.1" in out["note"]

    out2 = asyncio.run(api.ninjatrader_settings_save({"port": 8812}))
    assert out2["ninjatrader"]["port"] == 8812


def test_bridge_probe_reports_a_live_mock(monkeypatch):
    _stub(monkeypatch, _cfg())
    server = _running_mock(frames=2)
    out = asyncio.run(api.ninjatrader_test(
        {"host": "127.0.0.1", "port": server.port, "symbol": "NQ", "seconds": 1.5}))
    assert out["ok"] is True, out
    assert out["bridge"]["Addon"] == "modflow-nt-bridge"
    assert out["messages"]["quotes"] >= 1
    assert out["messages"]["trades"] >= 1
    subs = [f for f in server.received if f.get("Type") == "subscribe"]
    assert subs, "the probe should have subscribed"
    assert subs[0]["Instrument"] in ("NQ", "NQ 12-26")


def test_bridge_probe_says_where_to_look_when_nothing_listens(monkeypatch):
    _stub(monkeypatch, _cfg())
    out = asyncio.run(api.ninjatrader_test(
        {"host": "127.0.0.1", "port": _free_port(), "symbol": "NQ", "seconds": 0.5}))
    assert out["ok"] is False
    detail = str(out.get("detail") or "")
    assert "NinjaTrader" in detail


def test_dll_endpoint_reports_the_shipped_bridge(monkeypatch):
    _stub(monkeypatch, _cfg())
    out = asyncio.run(api.ninjatrader_dll())
    assert out["ok"] is True
    assert out["dll"]["exists"] is True
    assert out["dll"]["name"] == "ModFlowBridge.dll"
    assert "installed" in out
    assert out["note"]


# ── the instrument lane ───────────────────────────────────────────────────────────────

def test_resolve_offers_the_front_month_from_the_terminal(monkeypatch):
    _stub(monkeypatch, _cfg())
    monkeypatch.setattr(engine_mod, "ninjatrader_symbol_names",
                        lambda *a, **k: [{"Name": "NQ 12-26", "Root": "NQ", "Kind": "Future",
                                          "TickSize": 0.25}])
    out = asyncio.run(api.instruments_resolve(symbol="NQ1", broker=True))
    assert out["state"] == "available", out
    assert out["symbol"] == "NQ"
    assert out["broker_name"] == "NQ 12-26"
    assert out["actions"] == ["add", "open_instruments"]


def test_add_from_the_terminal_stamps_the_resolved_name(monkeypatch):
    cfg = _cfg()
    _stub(monkeypatch, cfg)
    monkeypatch.setattr(engine_mod, "ninjatrader_validate", lambda symbols: {
        "ok": True, "available": True,
        "symbols": {s: ({"listed": True, "tick_size": 0.25, "ninjatrader": "NQ 12-26"}
                         if s == "NQ" else {"listed": False, "tick_size": None, "ninjatrader": ""})
                    for s in symbols}})
    out = asyncio.run(api.instruments_add({"source": "ninjatrader", "symbols": ["NQ", "CL"]}))
    assert out["ok"] is True
    assert out["source"] == "ninjatrader"
    assert out["added"] == ["NQ"]
    row = next(r for r in cfg["instruments"] if r["symbol"] == "NQ")
    assert row["ninjatrader_symbol"] == "NQ 12-26"
    assert row["tick_size"] == 0.25
    assert row["asset_class"] == "Indices"
    assert out["skipped"] == [{"symbol": "CL", "reason": "your NinjaTrader terminal does not list CL"}]


def test_add_refuses_without_the_bridge(monkeypatch):
    _stub(monkeypatch, _cfg())
    monkeypatch.setattr(engine_mod, "ninjatrader_validate",
                        lambda symbols: {"ok": False, "available": False,
                                         "reason": "no bridge at 127.0.0.1:8790 (ConnectionRefusedError)",
                                         "symbols": {}})
    out = asyncio.run(api.instruments_add({"source": "ninjatrader", "symbols": ["NQ"]}))
    assert out["ok"] is False
    assert "bridge" in out["error"]
