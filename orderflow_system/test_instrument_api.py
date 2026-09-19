"""§82 — the instrument routes: look-up answers, broker search, source-aware adds, the ofx echo.

The routes are thin; the rules live in `desktop/instrument_lookup.py` (states/actions) and
`engine.select_instruments` (venue stamps). These pins cover the *interface*: what a typed
symbol is answered with, that the MT5 lane refuses without a terminal, that a symbol the
broker does not list is reported in `skipped` instead of written into the config, and that
`POST /ofx` now says whether what it stored can actually stream.
"""

from __future__ import annotations

import asyncio

from orderflow_system.desktop import api, config_store, engine as engine_mod


def _cfg(*, source: str = "mt5", enabled=("BTCUSDT",), extra=()) -> dict:
    rows = []
    for symbol in ("BTCUSDT", "NAS100USDT", "AAPL"):
        rows.append({"symbol": symbol, "asset_class": "Crypto" if symbol.endswith("USDT") else "Indices",
                     "enabled": symbol in enabled, "mt5_symbol": "" if symbol == "BTCUSDT" else "USTECm",
                     "bybit_symbol": "BTCUSDT" if symbol == "BTCUSDT" else "",
                     "alpaca_symbol": "AAPL" if symbol == "AAPL" else "",
                     "tick_size": 0.5})
    rows.extend(extra)
    return {"data_source": source, "instruments": rows, "mt5": {}, "ofx": {"symbol": ""}}


def _stub(monkeypatch, cfg: dict, *, running: bool, symbols=("BTCUSDT",), broker=()):
    monkeypatch.setattr(config_store, "load_config", lambda: cfg)
    monkeypatch.setattr(config_store, "save_config", lambda c: c)
    monkeypatch.setattr(engine_mod.engine, "status",
                        lambda: {"running": running, "symbols": list(symbols)})
    monkeypatch.setattr(engine_mod, "mt5_status", lambda: {"available": True, "reason": ""})
    monkeypatch.setattr(engine_mod, "mt5_symbol_names", lambda payload=None, refresh=False: {
        "ok": True, "available": True, "names": list(broker), "total": len(broker)})


# ── the look-up ──────────────────────────────────────────────────────────────────────

def test_resolve_answers_live_for_a_streaming_symbol(monkeypatch):
    _stub(monkeypatch, _cfg(), running=True)
    out = asyncio.run(api.instruments_resolve(symbol="BTCUSDT"))
    assert out["ok"] is True
    assert out["state"] == "live"
    assert out["actions"] == ["use"]


def test_resolve_maps_the_market_name_to_the_app_row(monkeypatch):
    cfg = _cfg(enabled=("BTCUSDT", "NAS100USDT"))
    _stub(monkeypatch, cfg, running=True, symbols=("BTCUSDT", "NAS100USDT"))
    out = asyncio.run(api.instruments_resolve(symbol="NQ1!"))
    assert out["symbol"] == "NAS100USDT"
    assert out["via"] == "alias"
    assert out["state"] == "live"


def test_resolve_says_disabled_with_the_action_to_fix_it(monkeypatch):
    _stub(monkeypatch, _cfg(), running=True)
    out = asyncio.run(api.instruments_resolve(symbol="NAS100USDT"))
    assert out["state"] == "disabled"
    assert out["actions"] == ["enable", "open_instruments"]
    assert "switched off" in out["reason"]


def test_resolve_calls_a_broker_name_available(monkeypatch):
    _stub(monkeypatch, _cfg(), running=True, broker=("NQZ25", "EURUSDm"))
    out = asyncio.run(api.instruments_resolve(symbol="NQZ25"))
    assert out["state"] == "available"
    assert out["actions"] == ["add", "open_instruments"]
    assert out["broker_total"] == 2


def test_resolve_does_not_ask_the_broker_when_the_source_is_crypto(monkeypatch):
    called = {"n": 0}

    def _boom(payload=None, refresh=False):
        called["n"] += 1
        return {"ok": True, "names": []}

    _stub(monkeypatch, _cfg(source="bybit"), running=True)
    monkeypatch.setattr(engine_mod, "mt5_symbol_names", _boom)
    out = asyncio.run(api.instruments_resolve(symbol="NQ1!"))
    assert called["n"] == 0
    # §82: the exchange lane cannot carry it at all, so the answer is the source's own refusal
    # (the reported "crypto only" message) with the way out — not a generic "enable it".
    assert out["state"] == "unsupported"
    assert "crypto only" in out["reason"]
    assert "MetaTrader 5" in out["hint"]


# ── the broker search ────────────────────────────────────────────────────────────────

def test_mt5_symbol_search_reports_the_missing_terminal_honestly(monkeypatch):
    monkeypatch.setattr(config_store, "load_config", lambda: _cfg())
    monkeypatch.setattr(engine_mod, "mt5_symbols", lambda payload=None, query="", limit=40: {
        "ok": False, "available": False, "reason": "the terminal did not accept the connection",
        "total": 0, "symbols": []})
    out = asyncio.run(api.mt5_symbol_list(q="NQ"))
    assert out["ok"] is False
    assert "terminal" in out["reason"]


def test_mt5_symbol_search_passes_the_query_through(monkeypatch):
    seen: dict = {}

    def _fake(payload=None, query="", limit=40):
        seen.update({"query": query, "limit": limit})
        return {"ok": True, "available": True, "total": 2,
                "symbols": [{"name": "NQZ25", "tick_size": 0.25}]}

    monkeypatch.setattr(config_store, "load_config", lambda: _cfg())
    monkeypatch.setattr(engine_mod, "mt5_symbols", _fake)
    out = asyncio.run(api.mt5_symbol_list(q="nq", limit=999))
    assert out["symbols"][0]["name"] == "NQZ25"
    assert seen == {"query": "nq", "limit": 200}, "the route clamps the limit"


# ── the adds ─────────────────────────────────────────────────────────────────────────

def test_add_source_choice_and_residue():
    cfg = {"data_source": "both"}
    assert api._add_source("mt5", cfg, ["NQZ25"]) == "mt5"
    assert api._add_source("", cfg, ["WIFUSDT"]) == "bybit"
    assert api._add_source("", cfg, ["NQZ25"]) == "mt5"
    assert api._add_source("", {"data_source": "alpaca"}, ["SPY"]) == "alpaca"
    assert api._add_source("nonsense", {"data_source": "okx"}, ["BTCUSDT"]) == "okx"


def test_add_via_mt5_writes_the_broker_stamp_and_the_venue_tick(monkeypatch):
    cfg = _cfg()
    _stub(monkeypatch, cfg, running=False)
    monkeypatch.setattr(engine_mod, "mt5_validate_symbols", lambda names, payload=None: {
        "ok": True, "available": True,
        "symbols": {name: {"listed": name == "NQZ25", "tick_size": 0.25 if name == "NQZ25" else None,
                           "description": "US Tech 100"} for name in names}})
    out = asyncio.run(api.instruments_add({"symbols": ["NQZ25", "NOPE"], "source": "mt5", "enable": True}))
    assert out["ok"] is True and out["source"] == "mt5"
    assert out["added"] == ["NQZ25"]
    assert out["skipped"] == [{"symbol": "NOPE", "reason": "the broker does not list NOPE"}]
    row = [i for i in out["config"]["instruments"] if i["symbol"] == "NQZ25"][0]
    assert row["mt5_symbol"] == "NQZ25"
    assert row["tick_size"] == 0.25
    assert row["enabled"] is True


def test_add_via_mt5_refuses_without_a_terminal(monkeypatch):
    cfg = _cfg()
    _stub(monkeypatch, cfg, running=False)
    monkeypatch.setattr(engine_mod, "mt5_validate_symbols", lambda names, payload=None: {
        "ok": False, "available": False, "reason": "the MetaTrader5 package is not installed", "symbols": {}})
    out = asyncio.run(api.instruments_add({"symbols": ["NQZ25"], "source": "mt5"}))
    assert out["ok"] is False
    assert "MetaTrader5" in out["error"]
    assert out["added"] == []


def test_add_via_bybit_keeps_the_wizards_contract(monkeypatch):
    cfg = _cfg(source="bybit")
    _stub(monkeypatch, cfg, running=False)
    monkeypatch.setattr(api, "_fetch_venue_catalog", lambda: {
        "WIFUSDT": {"symbol": "WIFUSDT", "tick_size": 0.0001, "status": "Trading"}})
    out = asyncio.run(api.instruments_add({"symbols": ["WIFUSDT"], "enable": True}))
    assert out["ok"] is True and out["source"] == "bybit"
    row = [i for i in out["config"]["instruments"] if i["symbol"] == "WIFUSDT"][0]
    assert row["bybit_symbol"] == "WIFUSDT" and row["tick_size"] == 0.0001 and row["enabled"] is True


def test_add_reports_a_symbol_that_vanishes_between_versions(monkeypatch):
    """A symbol the *matrix* knows is updated in place, never duplicated."""
    cfg = _cfg()
    _stub(monkeypatch, cfg, running=False)
    monkeypatch.setattr(engine_mod, "mt5_validate_symbols", lambda names, payload=None: {
        "ok": True, "available": True,
        "symbols": {name: {"listed": True, "tick_size": 1.0, "description": ""} for name in names}})
    before = len(cfg["instruments"])
    out = asyncio.run(api.instruments_add({"symbols": ["NAS100USDT"], "source": "mt5",
                                           "mt5_symbols": {"NAS100USDT": "US100"}, "enable": True}))
    assert out["updated"] == ["NAS100USDT"] and out["added"] == []
    assert len(out["config"]["instruments"]) == before
    row = [i for i in out["config"]["instruments"] if i["symbol"] == "NAS100USDT"][0]
    assert row["mt5_symbol"] == "US100" and row["tick_size"] == 1.0 and row["enabled"] is True


# ── the ofx echo ─────────────────────────────────────────────────────────────────────

def test_ofx_save_answers_with_the_stream_verdict(monkeypatch):
    cfg = _cfg()
    cfg["ofx"] = {"symbol": "NQ1!"}
    _stub(monkeypatch, cfg, running=True)
    out = asyncio.run(api.ofx_save({"symbol": "NQ1!"}))
    assert out["ok"] is True
    assert out["stream"]["symbol"] == "NAS100USDT"
    assert out["stream"]["state"] == "disabled"
    assert out["stream"]["actions"] == ["enable", "open_instruments"]


def test_ofx_save_with_an_empty_symbol_does_not_pretend(monkeypatch):
    _stub(monkeypatch, _cfg(), running=False)
    out = asyncio.run(api.ofx_save({"symbol": ""}))
    assert out["stream"]["state"] == "unknown"
    assert out["stream"]["reason"] == "type an instrument name"


# ── §82-ext: the Alpaca lane ─────────────────────────────────────────────────────────

def test_resolve_hands_the_linked_alpaca_assets_to_the_look_up(monkeypatch):
    cfg = _cfg(source="bybit")
    cfg["alpaca"] = {"key_id": "test-key-id", "secret": "test-secret"}
    _stub(monkeypatch, cfg, running=False)
    monkeypatch.setattr(api, "_alpaca_asset_symbols", lambda: ["SPY", "QQQ"])
    out = asyncio.run(api.instruments_resolve(symbol="SPY"))
    assert out["state"] == "available" and out["add_source"] == "alpaca"
    assert "add" in out["actions"] and "Alpaca" in out["reason"]


def test_the_assets_route_answers_unlinked_without_keys_and_serves_the_list_with_them(monkeypatch):
    cfg = _cfg(source="bybit")
    _stub(monkeypatch, cfg, running=False)
    out = asyncio.run(api.alpaca_assets())
    assert out["ok"] is True and out["linked"] is False and out["symbols"] == []
    linked = dict(cfg)
    linked["alpaca"] = {"key_id": "test-key-id", "secret": "test-secret"}
    monkeypatch.setattr(config_store, "load_config", lambda: linked)
    monkeypatch.setattr(api, "_alpaca_asset_symbols", lambda: ["SPY", "QQQ"])
    out2 = asyncio.run(api.alpaca_assets())
    assert out2["linked"] is True and out2["symbols"] == ["SPY", "QQQ"] and out2["total"] == 2


# ── MEM-B-09: the normalised Alpaca index is built once per refresh ──────────────────────────
def test_the_alpaca_index_is_built_once_per_refresh(monkeypatch):
    from orderflow_system.desktop import api, instrument_lookup

    class _Assets:
        def assets(self, force: bool = False):
            return [{"symbol": s} for s in ("SPY", "QQQ", "AAPL")]

    calls = {"n": 0}
    real = instrument_lookup.normalise

    def counting(value):
        calls["n"] += 1
        return real(value)

    monkeypatch.setattr(instrument_lookup, "normalise", counting)
    api._ALPACA_SYMBOLS_CACHE.update({"at": 0.0, "symbols": [], "by_norm": {}})
    monkeypatch.setattr(api, "_search_data", lambda: _Assets())

    symbols = api._alpaca_asset_symbols()
    warm = calls["n"]
    index = api._alpaca_asset_index()
    assert api._alpaca_asset_symbols() == symbols
    assert calls["n"] == warm, "a warm cache rebuilds no maps"
    assert index == {"SPY": "SPY", "QQQ": "QQQ", "AAPL": "AAPL"}

    cfg = {"instruments": [], "data_source": "alpaca"}
    calls["n"] = 0
    api._resolve_instrument("SPY", cfg, alpaca_names=symbols, alpaca_by_norm=index)
    with_index = calls["n"]
    calls["n"] = 0
    api._resolve_instrument("SPY", cfg, alpaca_names=symbols)
    without_index = calls["n"]
    assert with_index < without_index, \
        f"the prebuilt index skips the per-call map build ({with_index} vs {without_index})"
