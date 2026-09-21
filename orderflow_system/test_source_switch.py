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
def test_the_exchange_rules_no_longer_claim_usdt_named_non_crypto():
    """`endswith("USDT")` quietly claimed NAS100USDT (an index CFD) and XAUUSDT (gold) for every
    exchange venue — /datasources promised instruments the venue does not list."""
    from orderflow_system.desktop import engine as engine_mod

    for rule in (engine_mod.binance_capable, engine_mod.okx_capable, engine_mod.hyperliquid_capable):
        assert rule({"symbol": "NAS100USDT", "asset_class": "Indices"}) is False
        assert rule({"symbol": "XAUUSDT", "asset_class": "Metals"}) is False
        assert rule({"symbol": "BTCUSDT", "asset_class": "Crypto"}) is True


def test_select_instruments_skips_a_non_crypto_row_for_an_exchange_source():
    from orderflow_system.desktop import engine as engine_mod

    cfg = {"data_source": "binance", "instruments": [
        {"symbol": "BTCUSDT", "enabled": True},
        {"symbol": "NAS100USDT", "enabled": True, "asset_class": "Indices"},
    ]}
    selected, skipped = engine_mod.select_instruments(cfg)

    assert [i.instrument.value for i in selected] == ["BTCUSDT"]
    assert len(skipped) == 1 and "crypto" in skipped[0]["reason"], skipped


def test_the_bybit_extras_feed_runs_only_where_the_exchange_leg_does():
    """The extras book is a Bybit book: it may only be folded in when the exchange leg carries the
    symbols — the bybit source itself, or `both`/`all`, whose legs are partitioned so a symbol's
    prints and its depth come from the same venue."""
    import asyncio

    from orderflow_system.desktop import engine as engine_mod

    class _Cfg:
        tick_size = 0.1

    class _Pipeline:
        symbol = "BTCUSDT"
        config = _Cfg()

    class _Hub:
        def __init__(self) -> None:
            self.started: list[dict] = []

        async def start_feeds(self, symbols):
            self.started.append(symbols)
            return {"ok": True, "feeds": len(symbols)}

    class _System:
        def __init__(self, source: str) -> None:
            self._atlas_hub = _Hub()
            self.data_source = source
            self.pipelines = {"BTCUSDT": _Pipeline()}

    for source in ("binance", "okx", "hyperliquid", "mt5", "alpaca", "ninjatrader"):
        system = _System(source)
        asyncio.run(engine_mod._start_atlas_extras(system))
        assert system._atlas_hub.started == [], f"extras started under the {source} source"

    for source in ("bybit", "both", "all"):
        system = _System(source)
        asyncio.run(engine_mod._start_atlas_extras(system))
        assert system._atlas_hub.started, f"the {source} run's exchange leg must start its extras"

    # …and under a partitioned run, only the EXCHANGE leg's symbols get the exchange's depth
    class _MorePipelines(_System):
        def __init__(self, source):
            super().__init__(source)
            other = _Pipeline()
            other.symbol = "ETHUSDT"
            self.pipelines = {"BTCUSDT": _Pipeline(), "ETHUSDT": other}
            self._feed_symbols = {"bybit": ["ETHUSDT"], "mt5": ["BTCUSDT"], "alpaca": [],
                                  "ninjatrader": []}

    partitioned = _MorePipelines("both")
    asyncio.run(engine_mod._start_atlas_extras(partitioned))
    started = partitioned._atlas_hub.started
    assert started and list(started[-1]) == ["ETHUSDT"], started
    assert "BTCUSDT" not in started[-1], "a broker-mapped symbol must not get Bybit depth"

    # …but under a SINGLE-venue source nothing is partitioned, so the same table must not strand a
    # broker-stamped crypto symbol: BTCUSDT (mt5_symbol set by the wizard) lost its deep book,
    # liquidations and block trades while four lesser symbols kept theirs, because the extras read
    # a `both`-shaped partition that a `bybit` run never applies.
    stranded = _MorePipelines("bybit")
    asyncio.run(engine_mod._start_atlas_extras(stranded))
    assert set(stranded._atlas_hub.started[-1]) == {"BTCUSDT", "ETHUSDT"}, (
        "under `bybit` every exchange-servable symbol gets its extras — the partition means nothing")


def test_the_sources_sweep_is_cached_and_refreshable(monkeypatch):
    """Seven blocking probes ran on the event loop for every call (measured 2.7 s uncached)."""
    import asyncio

    from orderflow_system.desktop import api as api_mod

    monkeypatch.setattr(api_mod, "_SOURCES_CACHE", {"at": 0.0, "rows": None})
    calls = {"n": 0}

    def _probe(*_a, **_k):
        calls["n"] += 1
        return "ok"

    monkeypatch.setattr(api_mod, "_probe_source", _probe)

    # NB: called directly, the route's `refresh` default is FastAPI's Query object — truthy — so
    # the cached path is exercised by passing 0 explicitly (the HTTP layer always fills in an int).
    first = asyncio.run(api_mod.sources(refresh=0))
    second = asyncio.run(api_mod.sources(refresh=0))
    assert calls["n"] == len(api_mod.FREE_SOURCES), "the first call probes every source"
    assert second["sources"] == first["sources"] and calls["n"] == len(api_mod.FREE_SOURCES), \
        "the second call must answer from the cache"
    asyncio.run(api_mod.sources(refresh=1))
    assert calls["n"] == 2 * len(api_mod.FREE_SOURCES), "?refresh=1 must force a fresh sweep"
def test_partition_instruments_gives_every_symbol_exactly_one_venue():
    """`both`/`all` used to hand every enabled symbol to every leg: a doubly-mapped symbol
    streamed from two venues into one pipeline (doubled ticks/volume/delta)."""
    from orderflow_system.desktop import engine as engine_mod

    cfg = {"instruments": [
        {"symbol": "BTCUSDT", "enabled": True, "asset_class": "Crypto"},              # exchange only
        {"symbol": "ETHUSDT", "enabled": True, "asset_class": "Crypto",
         "mt5_symbol": "ETHUSDm"},                                                    # explicit broker
        {"symbol": "SOLUSDT", "enabled": True, "asset_class": "Crypto",
         "alpaca_symbol": "SOL/USD"},   # the wizard's Alpaca crypto map must NOT steal the exchange
        {"symbol": "NAS100USDT", "enabled": True, "asset_class": "Indices",
         "mt5_symbol": "USTEC"},                                                      # broker, mapped
        {"symbol": "XAUUSDT", "enabled": True, "asset_class": "Metals"},               # broker, unmapped
        {"symbol": "AAPL", "enabled": True, "asset_class": "Stocks",
         "alpaca_symbol": "AAPL", "mt5_symbol": "AAPL"},
        {"symbol": "NQ1!", "enabled": True, "ninjatrader_symbol": "NQ 12-26"},
        {"symbol": "DOGEUSDT", "enabled": False, "asset_class": "Crypto"},             # disabled
    ]}
    selected = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "NAS100USDT", "XAUUSDT", "AAPL", "NQ1!"]

    # `both` starts the exchange and the broker only: a stamp for a leg this run does NOT start
    # must fall through (measured live: Alpaca-mapped crypto used to land on the unstarted leg and
    # the board streamed nothing at all).
    both = engine_mod.partition_instruments(cfg, selected, legs=("bybit", "mt5"))
    assert both["bybit"] == ["BTCUSDT", "SOLUSDT"], both
    # AAPL falls through its (unstarted) Alpaca stamp to the broker, and NQ1! likewise when the
    # NinjaTrader leg is not part of the run — MT5 is the only other venue that can carry them.
    assert set(both["mt5"]) == {"ETHUSDT", "NAS100USDT", "XAUUSDT", "AAPL", "NQ1!"}, both
    assert both["alpaca"] == [] and both["ninjatrader"] == [], "an unstarted leg gets nothing"

    every = [s for s in selected if any(s in leg for leg in both.values())]
    assert sorted(every) == sorted(selected), "every selected symbol lands on exactly one venue"

    # `all` starts every leg, so the stamps get their own venues back
    full = engine_mod.partition_instruments(cfg, selected)
    assert full["alpaca"] == ["AAPL"] and full["ninjatrader"] == ["NQ1!"], full
    assert full["bybit"] == ["BTCUSDT", "SOLUSDT"], full       # crypto never rides Alpaca's quotes
    assert "ETHUSDT" in full["mt5"], full


def test_the_both_and_all_legs_use_the_partition():
    """Source pin: the legs read the partition instead of handing out the blanket symbol list."""
    from pathlib import Path

    main_src = Path("orderflow_system/main.py").read_text(encoding="utf-8")
    assert "DataSource.BYBIT, DataSource.BOTH, DataSource.ALL" in main_src, "the Bybit leg ignores `all`"
    assert 'partition["bybit"]' in main_src and 'partition["mt5"]' in main_src
    assert 'partition["alpaca"]' in main_src and 'partition["ninjatrader"]' in main_src
    assert "MT5 leg skipped" in main_src, "an empty leg must be announced, not silently blank"


def test_each_source_hint_names_what_it_carries():
    """The Data menu shows each venue's hint on hover — it must say what the venue carries,
    not only how to reach it (the "where do I get index funds?" hunt)."""
    hints = {sid: hint for sid, _name, hint, _url, _wired in api.FREE_SOURCES}
    for crypto_only in ("bybit", "binance", "okx", "hyperliquid"):
        assert "crypto only" in hints[crypto_only], crypto_only
    assert "index CFDs" in hints["mt5"]
    assert "ETFs" in hints["alpaca"]
    assert "index futures" in hints["ninjatrader"]
