"""§87 — the Market Watch board and the Run menu's launcher, pinned.

The board's job is the same as the Systems board's: say what is true. The MT5 branch mirrors the
running terminal's own Market Watch and must never write to it (no symbol_select — proven by a
booby-trapped fake below); the Bybit branch is one cached whole-board snapshot; NinjaTrader lists
its master instruments and admits its bridge only carries subscribed ones. The launcher refuses
closed-set violations, a frozen build asked for the CLI pipeline, and a busy port 8099.
"""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys

from orderflow_system.desktop import api, config_store, engine as engine_mod, marketwatch as mw


# ── the Bybit board ─────────────────────────────────────────────────────────────────────

def _tickers():
    return {"result": {"list": [
        {"symbol": "ETHUSDT", "bid1Price": "3000.1", "ask1Price": "3000.2", "lastPrice": "3000.1", "price24hPcnt": "-0.0210"},
        {"symbol": "BTCUSDT", "bid1Price": "60000", "ask1Price": "60001", "lastPrice": "60000.5", "price24hPcnt": "0.0123"},
        {"symbol": "ADAUSDT", "bid1Price": "0.5", "ask1Price": "0.51", "lastPrice": "0.505", "price24hPcnt": "0"},
    ]}}


class _FakeHTTP:
    def __init__(self, payload): self.payload = payload
    def read(self): return json.dumps(self.payload).encode()
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_bybit_snapshot_is_one_call_and_sorted(monkeypatch):
    mw._TICKERS.update({"at": 0.0, "rows": []})
    calls = {"n": 0}

    def fake_urlopen(request, timeout=6):
        calls["n"] += 1
        return _FakeHTTP(_tickers())

    monkeypatch.setattr(mw.urllib.request, "urlopen", fake_urlopen)
    first = mw._bybit_board()
    second = mw._bybit_board()                      # cached — the venue is asked once per TTL
    assert calls["n"] == 1
    assert [r["symbol"] for r in first] == ["ADAUSDT", "BTCUSDT", "ETHUSDT"]   # sorted
    assert first[1]["change_pct"] == 1.23           # price24hPcnt is a fraction → percent
    assert first[2]["change_pct"] == -2.1
    assert second == first


def test_bybit_filter_limit_offset_note(monkeypatch):
    monkeypatch.setattr(mw, "_bybit_board", lambda: [
        {"symbol": s, "bid": 1.0, "ask": 1.1, "last": 1.0, "change_pct": 0.0}
        for s in ("ADAUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT")])
    monkeypatch.setattr(mw, "_exchange_board",
                        lambda venue, **kw: [{"symbol": "ETHUSDT", "bid": 0, "ask": 0,
                                              "last": 0, "change_pct": 0, "quoted": False}])
    page = mw.market_watch("bybit", filter_text="usdt", limit=2, offset=1)
    assert page["ok"] is True and page["total"] == 4 and page["offset"] == 1
    assert [r["symbol"] for r in page["rows"]] == ["BTCUSDT", "ETHUSDT"]
    assert "Bybit" in page["note"] and "filter" in page["note"]
    # Each exchange venue now answers with ITS OWN board (before: every one answered with Bybit's)
    other = mw.market_watch("binance")
    assert other["source"] == "binance" and "Binance" in other["note"], other


# ── the MT5 mirror ──────────────────────────────────────────────────────────────────────

class _FakeSymbol:
    def __init__(self, name, path, visible):
        self.name, self.path, self.visible = name, path, visible


class _FakeTick:
    def __init__(self, bid, ask):
        self.bid, self.ask, self.last = bid, ask, bid


class _FakeMT5:
    """Booby-trapped: any write to the terminal (symbol_select) fails the test that uses it."""

    TIMEFRAME_D1 = 1440

    def symbols_get(self):
        return [_FakeSymbol("EURUSD", "Forex\\Major", True),
                _FakeSymbol("AMD", "Stocks\\US", True),
                _FakeSymbol("HIDDENX", "Stocks\\US", False)]

    def symbol_info_tick(self, symbol):
        return {"EURUSD": _FakeTick(1.14763, 1.14764), "AMD": _FakeTick(219.01, 219.05)}.get(symbol)

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        opening = {"EURUSD": 1.1543, "AMD": 210.0}.get(symbol)
        return None if opening is None else [{"open": opening}, {"open": opening}]

    def symbol_select(self, *a, **k):
        raise AssertionError("the market watch must never write to the terminal")

    def shutdown(self):
        pass


def test_mt5_mirrors_the_terminal_read_only(monkeypatch):
    monkeypatch.setattr(engine_mod, "_mt5_begin", lambda payload=None: (_FakeMT5(), ""))
    board = mw.market_watch("mt5")
    assert board["ok"] is True and board["total"] == 2          # HIDDENX (not visible) never listed
    assert [r["symbol"] for r in board["rows"]] == ["EURUSD", "AMD"]
    eur = board["rows"][0]
    assert eur["bid"] == 1.14763 and eur["quoted"] is True
    assert eur["change_pct"] == -0.58                            # (1.14763 − 1.1543) / 1.1543
    assert "Market Watch" in board["note"] and "mirroring" in board["note"]


def test_mt5_daily_open_is_cached_between_polls(monkeypatch):
    """The live poll re-reads the tick; the *daily* basis is fetched once and cached."""
    calls = {"rates": 0}

    class CountingMT5(_FakeMT5):
        def copy_rates_from_pos(self, symbol, timeframe, start, count):
            calls["rates"] += 1
            return super().copy_rates_from_pos(symbol, timeframe, start, count)

    monkeypatch.setattr(engine_mod, "_mt5_begin", lambda payload=None: (CountingMT5(), ""))
    mw._MT5_OPEN.clear()
    first = mw.market_watch("mt5")
    second = mw.market_watch("mt5")          # the second poll: two symbols, no new rate reads
    assert calls["rates"] == 2
    assert first["rows"][0]["change_pct"] == second["rows"][0]["change_pct"]


def test_mt5_daily_open_cache_expires(monkeypatch):
    calls = {"rates": 0}

    class CountingMT5(_FakeMT5):
        def copy_rates_from_pos(self, symbol, timeframe, start, count):
            calls["rates"] += 1
            return super().copy_rates_from_pos(symbol, timeframe, start, count)

    monkeypatch.setattr(engine_mod, "_mt5_begin", lambda payload=None: (CountingMT5(), ""))
    mw._MT5_OPEN.clear()
    monkeypatch.setattr(mw, "_MT5_OPEN_TTL_S", 0.0)
    mw.market_watch("mt5")
    mw.market_watch("mt5")
    assert calls["rates"] == 4


def test_mt5_unavailable_says_why(monkeypatch):
    monkeypatch.setattr(engine_mod, "_mt5_begin", lambda payload=None: (None, "terminal not running"))
    board = mw.market_watch("mt5")
    assert board["ok"] is False and board["rows"] == [] and board["note"] == "terminal not running"


# ── NinjaTrader and the honest refusal ──────────────────────────────────────────────────

def test_ninjatrader_lists_master_instruments(monkeypatch):
    monkeypatch.setattr(engine_mod, "ninjatrader_symbol_names",
                        lambda: [{"Name": "NQ DEC26"}, {"Name": "ES DEC26"}])
    board = mw.market_watch("ninjatrader", filter_text="nq")
    assert board["ok"] is True and [r["symbol"] for r in board["rows"]] == ["NQ DEC26"]
    assert board["rows"][0]["quoted"] is False
    assert "subscribed" in board["note"]


def test_unknown_source_has_no_board():
    board = mw.market_watch("alpaca")
    assert board["ok"] is False and "no board of its own" in board["note"]


# ── the routes ──────────────────────────────────────────────────────────────────────────

def test_marketwatch_route_defaults_to_the_engine_source(monkeypatch):
    seen = {}

    def fake(source, filter_text, limit, offset):
        seen.update({"source": source, "limit": limit})
        return {"ok": True, "rows": [], "total": 0}

    monkeypatch.setattr(mw, "market_watch", fake)
    monkeypatch.setattr(config_store, "load_config", lambda: {"data_source": "mt5"})
    out = asyncio.run(api.marketwatch(source="", filter="", limit=10, offset=0))
    assert out["ok"] is True and seen == {"source": "mt5", "limit": 10}


def test_launch_refuses_unknown_modes():
    out = asyncio.run(api.launch_mode({"mode": "carrier-pigeon"}))
    assert out == {"ok": False, "error": "unknown mode — 'headless' or 'cli'"}


def test_launch_refuses_the_cli_pipeline_on_a_frozen_build(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    out = asyncio.run(api.launch_mode({"mode": "cli"}))
    assert out["ok"] is False and "source tree" in out["error"]


def test_launch_refuses_when_8099_already_answers(monkeypatch):
    class _Open:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: _Open())
    out = asyncio.run(api.launch_mode({"mode": "headless"}))
    assert out["ok"] is False and "already answering" in out["error"]


def test_launch_headless_spawns_its_own_console(monkeypatch):
    monkeypatch.setattr(socket, "create_connection",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("closed")))
    seen = {}

    class _Proc:
        pid = 4242

    def fake_popen(args, cwd=None, creationflags=0):
        seen.update({"args": args, "cwd": cwd, "creationflags": creationflags})
        return _Proc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    out = asyncio.run(api.launch_mode({"mode": "headless"}))
    assert out["ok"] is True and out["pid"] == 4242
    assert "--headless" in seen["args"] and "8099" in seen["args"]
    assert "history store" in out["note"]           # the honest sentence about the shared store
    assert seen["creationflags"] == getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
