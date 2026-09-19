"""The palette's per-row cost: one search must not re-read the config per asset row.

MEM-B-01 (P0) / MEM-B-02 (P1) — the row builder and the live pump used to reload and re-merge
the whole config once per symbol (measured: 4,055 loads / 7.5 s of event-loop freeze per
keystroke on a linked account). These pins drive the *real* route wiring with a 4,000-row
asset fixture and count ``config_store.load_config`` calls.
"""

from __future__ import annotations

import asyncio

from orderflow_system.desktop import api


class _Assets:
    """The Alpaca asset-list seam (network stand-in) with ``n`` tradable rows."""

    def __init__(self, n: int) -> None:
        self._rows = [{"symbol": f"S{i:04d}", "name": f"Stock {i}", "class": "us_equity",
                       "exchange": "NASDAQ", "tradable": True} for i in range(n)]

    def assets(self, force: bool = False) -> list[dict]:
        return list(self._rows)


class _Tick:
    def __init__(self, price: float, size: float) -> None:
        self.price = price
        self.size = size


class _System:
    """A live-engine stand-in: pipelines and recent ticks, enough for the row builder."""

    alpaca_feed = None

    def __init__(self, symbols) -> None:
        self.pipelines = {s: object() for s in symbols}

    def recent_ticks(self, symbol, n):
        return [_Tick(100.0 + i, 1.0) for i in range(min(n, 16))]


_CFG = {
    "data_source": "alpaca",
    "alpaca": {"key_id": "key", "secret": "secret", "feed": "iex"},
    "instruments": [{"symbol": "BTCUSDT", "enabled": True, "alpaca_symbol": "BTC/USD"}],
    "search": {"pins": ["SPY"], "recents": ["AAPL"]},
}


def _palette_fixture(monkeypatch, n_assets: int, symbols=("BTCUSDT",)) -> dict:
    """Wire the palette the way the route does, with a counting ``load_config``."""
    calls = {"n": 0}

    def counting_load():
        calls["n"] += 1
        return _CFG

    monkeypatch.setattr(api.config_store, "load_config", counting_load)
    monkeypatch.setattr(api, "_search_data", lambda: _Assets(n_assets))
    monkeypatch.setattr(api.engine_mod.engine, "_system", _System(symbols))
    return calls


def test_one_search_reads_the_config_a_bounded_number_of_times(monkeypatch):
    """A 4,000-row universe must not turn one keystroke into thousands of config loads."""
    small = _palette_fixture(monkeypatch, 200)
    payload_small = asyncio.run(api.search_symbols(q="S0000", limit=20, sort="relevance", types=""))
    small_count = small["n"]

    big = _palette_fixture(monkeypatch, 4000)
    payload_big = asyncio.run(api.search_symbols(q="S0000", limit=20, sort="relevance", types=""))
    big_count = big["n"]

    # the fixture really is the whole universe, not a truncated one
    assert payload_small["assets"] == 200 and payload_big["assets"] == 4000
    assert payload_big["rows"] and payload_big["rows"][0]["symbol"] == "S0000"
    assert payload_big["rows"][0]["last"] is not None      # the live path really ran
    # the per-row config read is gone: the count is constant, and small
    assert small_count <= 6 and big_count <= 6, (small_count, big_count)
    assert big_count == small_count, (small_count, big_count)


def test_the_ctx_is_one_read_reused_within_the_ttl(monkeypatch):
    calls = _palette_fixture(monkeypatch, 1)
    api._SEARCH["ctx"] = None
    first = api._search_live_ctx()
    second = api._search_live_ctx()
    assert first is second
    assert calls["n"] == 1


def test_the_pump_flush_reads_the_config_once_not_per_symbol(monkeypatch):
    """40 visible symbols, two flushes: one config read, 80 offered rows."""
    from orderflow_system.desktop.search_service import RowBatcher

    active = [f"SYM{i:02d}" for i in range(40)]
    calls = _palette_fixture(monkeypatch, 10, symbols=active)
    api._SEARCH["batcher"] = RowBatcher()
    api._SEARCH["active"] = list(active)
    api._SEARCH["ctx"] = None

    assert api._search_pump_tick() == []                # the first tick opens the window
    assert api._SEARCH["batcher"].pending() == 40
    assert calls["n"] <= 1, calls["n"]

    api._SEARCH["batcher"]._last_flush_ms -= 10_000     # the batch window closes
    rows = api._search_pump_tick()
    assert len(rows) == 40
    assert calls["n"] <= 1, calls["n"]                  # inside the TTL: still no extra read

    # a tick whose window is still open costs nothing at all
    assert api._search_pump_tick() == []
    assert calls["n"] <= 1
