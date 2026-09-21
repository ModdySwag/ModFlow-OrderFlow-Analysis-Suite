"""
Integration tests: alert rules, depth book, FeatureHub wiring, Market Replay.

Run:  .venv/Scripts/python.exe -m pytest orderflow_system/test_atlas_integration.py -v
"""

from __future__ import annotations

import asyncio
import sqlite3


from orderflow_system.atlas.alerts import AlertEngine, DEFAULT_RULES
from orderflow_system.atlas.feed_extras import BybitDepthBook
from orderflow_system.atlas.hub import FeatureHub
from orderflow_system.atlas.replay import MarketReplay
from orderflow_system.atlas.tapeflow import BigTrade, SweepEvent
from orderflow_system.data.models import Side, Tick

T0 = 1_700_000_000_000


def tick(ts: int, price: float, size: float, side: str = "buy") -> Tick:
    return Tick(timestamp_ms=ts, price=price, size=size, side=Side.BUY if side == "buy" else Side.SELL)


# ── alerts ──────────────────────────────────────────────────────────────────

def test_alert_rules_right_kind_and_thresholds():
    engine = AlertEngine()
    big = BigTrade(ts_ms=T0, price=100.0, size=10.0, side="buy", multiple=2.0)

    fired = engine.evaluate("T", "big_trade", big, ts_ms=T0)
    assert len(fired) == 1 and fired[0].kind == "big_trade"

    small = BigTrade(ts_ms=T0, price=100.0, size=1.0, side="buy", multiple=0.5)
    assert engine.evaluate("T", "big_trade", small, ts_ms=T0) == []          # below min_multiple


def test_alert_cooldown_blocks_repeats():
    engine = AlertEngine(rules=[{"id": "r", "name": "sweep", "kind": "sweep",
                                 "params": {"min_levels": 3}, "cooldown_s": 30}])
    sweep = SweepEvent(ts_ms=T0, side="buy", levels=5, size=10.0, from_price=100.0, to_price=104.0, duration_ms=50)
    assert len(engine.evaluate("T", "sweep", sweep, ts_ms=T0)) == 1
    assert engine.evaluate("T", "sweep", sweep, ts_ms=T0 + 1000) == []        # inside cooldown
    assert len(engine.evaluate("T", "sweep", sweep, ts_ms=T0 + 31_000)) == 1   # after cooldown


def test_alert_disabled_rule_never_fires():
    engine = AlertEngine(rules=[{"id": "off", "name": "off", "kind": "stop_run", "enabled": False, "params": {}}])
    assert engine.evaluate("T", "stop_run", {"ticks_moved": 100.0}, ts_ms=T0) == []


def test_alert_rule_crud_and_stats():
    engine = AlertEngine()
    n = len(engine.rules)
    engine.upsert({"id": "new", "name": "custom", "kind": "iceberg", "params": {"min_fills": 2}})
    assert len(engine.rules) == n + 1
    engine.upsert({"id": "new", "name": "custom2", "kind": "iceberg", "params": {"min_fills": 9}})
    assert len(engine.rules) == n + 1                                        # upsert, not append
    engine.remove("new")
    assert len(engine.rules) == n
    assert engine.stats()["rules"] == n
    assert {r["kind"] for r in DEFAULT_RULES} >= {"big_trade", "sweep", "stop_run", "iceberg", "speed_spike"}


def test_alert_cvd_divergence_kind_filter():
    engine = AlertEngine(rules=[{"id": "d", "name": "div", "kind": "cvd_divergence",
                                 "params": {"kinds": ["bearish"], "min_strength": 0}}])
    assert engine.evaluate("T", "cvd_divergence", {"kind": "bullish", "strength": 90}, ts_ms=T0) == []
    assert len(engine.evaluate("T", "cvd_divergence", {"kind": "bearish", "strength": 90}, ts_ms=T0 + 1)) == 1


# ── depth book ──────────────────────────────────────────────────────────────

def test_bybit_depth_book_snapshot_and_deltas():
    book = BybitDepthBook("T")
    book.apply("snapshot", {"b": [["100.0", "5"], ["99.0", "3"]], "a": [["101.0", "4"]], "u": 1})
    snap = book.to_snapshot()
    assert snap.best_bid == 100.0 and snap.best_ask == 101.0

    book.apply("delta", {"b": [["99.0", "0"], ["98.5", "7"]], "a": [["101.0", "9"]], "u": 2})
    snap = book.to_snapshot()
    prices = {l.price for l in snap.bids}
    assert 99.0 not in prices and 98.5 in prices            # delete + insert
    assert next(l for l in snap.asks if l.price == 101.0).quantity == 9.0


# ── hub ─────────────────────────────────────────────────────────────────────

def test_hub_end_to_end_counts_and_alerts():
    hub = FeatureHub({
        "tape": {"sweep_levels": 3},                        # config-driven tuning
        "alert_rules": [
            {"id": "b", "name": "big", "kind": "big_trade", "params": {"min_multiple": 1.0}, "cooldown_s": 0},
            {"id": "s", "name": "sweep", "kind": "sweep", "params": {"min_levels": 3}, "cooldown_s": 0},
        ],
    })
    assert hub.symbols.get("BTCUSDT") is None

    for i in range(120):                                    # baseline distribution
        hub.on_tick("BTCUSDT", tick(T0 + i, 100.0, 1.0))
    thr = hub.symbols["BTCUSDT"].tape.big_threshold()

    hub.on_tick("BTCUSDT", tick(T0 + 200, 100.0, thr * 5, "sell"))            # big trade
    for i in range(4):                                                        # a sweep
        hub.on_tick("BTCUSDT", tick(T0 + 300 + i * 10, 101.0 + i, 2.0, "buy"))

    st = hub.status()
    assert st["counters"]["ticks"] == 125
    assert st["alerts"]["history"] >= 2
    kinds = {a["kind"] for a in hub.alerts.recent(20)}
    assert "big_trade" in kinds and "sweep" in kinds
    assert hub.snapshot_tape("BTCUSDT")["stats"]["big_trades"] >= 1


def test_hub_heatmap_and_profile_snapshots():
    hub = FeatureHub()
    from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot
    book = OrderbookSnapshot(timestamp_ms=T0, bids=[OrderbookLevel(price=100.0, quantity=9.0)],
                             asks=[OrderbookLevel(price=101.0, quantity=4.0)])
    hub.on_orderbook("BTCUSDT", book)
    for i in range(30):
        hub.on_tick("BTCUSDT", tick(T0 + i * 100, 100.0 + (i % 3) * 0.5, 1.0))

    heat = hub.snapshot_heatmap("BTCUSDT")
    assert heat["values"] and len(heat["values"]) == len(heat["prices"])
    assert hub.snapshot_cvd("BTCUSDT")["cvd"] != 0.0
    prof = hub.snapshot_profile("BTCUSDT")
    assert prof["poc"] in (100.0, 100.5, 101.0)
    assert hub.snapshot_frames("BTCUSDT", "tick")["bars"] is not None


def test_hub_clear_resets_state():
    hub = FeatureHub()
    for i in range(10):
        hub.on_tick("X", tick(T0 + i, 10.0, 1.0))
    hub.clear()
    assert hub.snapshot_cvd("X")["cvd"] == 0.0
    assert hub.snapshot_profile("X")["levels"] == []


# ── replay ──────────────────────────────────────────────────────────────────

def _make_db(path: str, rows: list[tuple]) -> None:
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE ticks (id INTEGER PRIMARY KEY AUTOINCREMENT, instrument TEXT,
                   timestamp_ms INTEGER, price REAL, size REAL, side TEXT, trade_id TEXT)""")
    con.execute("""CREATE TABLE candles (id INTEGER PRIMARY KEY AUTOINCREMENT, instrument TEXT,
                   timestamp_ms INTEGER, timeframe TEXT, open REAL, high REAL, low REAL, close REAL,
                   volume REAL, buy_volume REAL, sell_volume REAL, delta REAL, tick_count INTEGER,
                   footprint_json TEXT)""")
    con.executemany("INSERT INTO ticks (instrument, timestamp_ms, price, size, side) VALUES (?,?,?,?,?)", rows)
    con.commit()
    con.close()


def test_replay_streams_recorded_ticks_in_order(tmp_path):
    db = str(tmp_path / "replay.db")
    rows = [("BTCUSDT", T0 + i * 100, 100.0 + i, 1.0 + i % 3, "buy" if i % 2 else "sell") for i in range(50)]
    rows.append(("OTHER", T0, 1.0, 1.0, "buy"))                      # must be ignored
    _make_db(db, rows)

    replay = MarketReplay(db, speed=1000.0, max_gap_ms=0)
    loaded = asyncio.run(_replay_roundtrip(replay, "BTCUSDT"))

    assert loaded["mode"] == "ticks"
    assert loaded["seen"] == 50
    assert loaded["ordered"] is True
    assert loaded["prices"][0] == 100.0 and loaded["prices"][-1] == 149.0
    assert loaded["sides"] == {"buy", "sell"}
    assert loaded["status"]["state"] == "finished"
    assert loaded["status"]["progress_pct"] == 100.0


def test_a_failed_replay_load_keeps_no_stale_rows_or_counts(tmp_path):
    """MEM-A1-11: reset at the head of a load — a failed load must not leave the previous
    symbol's tape playing under the new label, and the rows must be released."""
    db = str(tmp_path / "replay_stale.db")
    _make_db(db, [("X", T0 + i * 10, 50.0 + i, 1.0, "buy") for i in range(40)])
    replay = MarketReplay(db, speed=1000.0, max_gap_ms=0)

    async def scenario():
        await replay.load("X")
        assert replay.status()["total"] == 40

        # the second load fails (a DB that is not there)...
        broken = MarketReplay(str(tmp_path / "missing.db"), speed=1000.0)
        broken._rows = list(replay._rows)               # pretend it held a tape before
        out = await broken.load("Y")
        # ...and leaves nothing behind: not the old rows, not the old counts
        assert out["state"] in ("idle", "error") and out["total"] == 0 and broken._rows == []
        assert out["symbol"] == "Y"

        # and `reset()` really releases a loaded tape (the route's path — MEM-A1-11)
        replay.reset()
        assert replay._rows == [] and replay.status()["total"] == 0

    asyncio.run(scenario())


def test_hub_emissions_are_tracked_and_cancelled_on_shutdown():
    """MEM-A1-06: the three fire-and-forget paths are owned by the hub now."""

    async def scenario():
        hub = FeatureHub({})
        started = asyncio.Event()

        async def stalled_sink(channel, symbol, data):
            started.set()
            await asyncio.Event().wait()                 # a wedged sink

        hub.set_sink(stalled_sink)
        for i in range(5):
            hub._emit("alert", "BTCUSDT", {"i": i})
        await asyncio.wait_for(started.wait(), 1.0)
        assert len(hub._tasks) == 5, "every spawned task is held by the hub"

        await hub.shutdown()
        assert hub._tasks == set(), "shutdown cancels and releases them"

        # finished work is discarded, not accumulated
        async def quick_sink(channel, symbol, data):
            return None

        hub.set_sink(quick_sink)
        for _ in range(20):
            hub._emit("alert", "BTCUSDT", {})
        await asyncio.sleep(0.05)
        assert hub._tasks == set(), "completed emissions do not pile up"

    asyncio.run(scenario())


def test_the_hub_symbol_map_is_capped_with_streamed_symbols_protected():
    """MEM-A1-08: REST can ask about any symbol; the map is capped and streamed symbols stay."""
    hub = FeatureHub({})
    hub.register("BTCUSDT")
    for i in range(200):
        hub.ensure(f"FOO{i}")
    assert len(hub.symbols) <= hub.MAX_REST_SYMBOLS
    assert "BTCUSDT" in hub.symbols, "a registered (streamed) symbol is never evicted"
    assert "FOO199" in hub.symbols, "the newest REST symbol is the one that stays"


async def _replay_roundtrip(replay: MarketReplay, symbol: str) -> dict:
    await replay.load(symbol)
    seen: list[Tick] = []

    async def collect(t: Tick) -> None:
        seen.append(t)

    await replay.play(collect)
    assert replay._task is not None
    await replay._task
    prices = [t.price for t in seen]
    return {
        "mode": replay.status()["mode"],
        "seen": len(seen),
        "ordered": prices == sorted(prices),
        "prices": prices,
        "sides": {("buy" if t.side == Side.BUY else "sell") for t in seen},
        "status": replay.status(),
    }


def test_replay_pause_resume_seek(tmp_path):
    db = str(tmp_path / "replay2.db")
    _make_db(db, [("X", T0 + i * 10, 50.0 + i, 1.0, "buy") for i in range(100)])
    replay = MarketReplay(db, speed=1000.0, max_gap_ms=0)

    async def scenario() -> dict:
        await replay.load("X")
        seen = []

        async def collect(t: Tick) -> None:
            seen.append(t)
            if len(seen) == 5:
                replay.pause()

        await replay.play(collect)
        await asyncio.sleep(0.2)
        paused_state = replay.status()["state"]
        paused_count = len(seen)
        replay.seek(90)
        replay.resume()
        await asyncio.sleep(0.4)
        replay.set_speed(1.0)
        assert replay.status()["speed"] == 1.0
        index_after_seek = replay.status()["index"]
        last_price = seen[-1].price if seen else 0.0
        await replay.stop()
        return {"paused_state": paused_state, "paused_count": paused_count,
                "index_after_seek": index_after_seek, "last_price": last_price,
                "final_state": replay.status()["state"]}

    out = asyncio.run(scenario())
    assert out["paused_state"] == "paused"
    assert out["paused_count"] == 5                    # paused exactly at the 5th print
    assert out["index_after_seek"] >= 90, out           # seek jumped to row 90+
    assert out["last_price"] >= 149.0                   # …and streamed to the end of the file
    assert out["final_state"] == "idle"


def test_replay_seek_while_paused_applies_immediately(tmp_path):
    """Scrubbing the transport while paused must move the position at once.

    The playback loop only consumes a pending seek while it is running, so a
    paused seek used to leave the slider/clock on the old row until a resume
    that might never come — which reads as a dead control in the UI.
    """
    db = str(tmp_path / "replay-seek.db")
    _make_db(db, [("X", T0 + i * 10, 50.0 + i, 1.0, "buy") for i in range(100)])
    replay = MarketReplay(db, speed=1000.0, max_gap_ms=0)

    async def scenario() -> dict:
        await replay.load("X")
        seen = []

        async def collect(t: Tick) -> None:
            seen.append(t)
            if len(seen) == 3:
                replay.pause()

        await replay.play(collect)
        await asyncio.sleep(0.2)
        before = replay.status()
        after = replay.seek_fraction(0.5)
        await asyncio.sleep(0.1)
        still = replay.status()
        replay.resume()
        await asyncio.sleep(0.3)
        await replay.stop()
        return {"state": before["state"], "before_index": before["index"],
                "after_index": after["index"], "still_index": still["index"],
                "still_clock": still["current_ms"], "total": still["total"]}

    out = asyncio.run(scenario())
    assert out["state"] == "paused"
    assert out["after_index"] == 50
    assert out["still_index"] == 50                      # holds while still paused
    assert out["still_clock"] == T0 + 500                # clock follows the scrub


def test_replay_falls_back_to_candles(tmp_path):
    db = str(tmp_path / "replay3.db")
    _make_db(db, [])
    con = sqlite3.connect(db)
    con.executemany("INSERT INTO candles (instrument, timestamp_ms, timeframe, close, volume, delta) VALUES (?,?,?,?,?,?)",
                    [("X", T0 + i * 60_000, "1m", 100.0 + i, 5.0, 2.0 if i % 2 else -3.0) for i in range(10)])
    con.commit()
    con.close()

    replay = MarketReplay(db, speed=1000.0, max_gap_ms=0)

    async def run() -> dict:
        await replay.load("X")
        seen = []

        async def collect(t: Tick) -> None:
            seen.append(t)

        await replay.play(collect)
        await replay._task                          # type: ignore[union-attr]
        return {"mode": replay.status()["mode"], "n": len(seen),
                "sides": {("buy" if t.side == Side.BUY else "sell") for t in seen}}

    out = asyncio.run(run())
    assert out["mode"] == "candles"
    assert out["n"] == 10
    assert out["sides"] == {"buy", "sell"}           # delta sign decides the side


def test_replay_exchange_loader_is_offline_safe(tmp_path):
    """The exchange seed must fail soft (no crash) when the network is unavailable."""
    replay = MarketReplay(str(tmp_path / "none.db"), speed=100.0)

    async def run() -> dict:
        return await replay.load_from_exchange("NOTAREALSYMBOL12345", limit=5)

    out = asyncio.run(run())
    assert out["state"] in ("error", "idle", "loaded")
    assert out["total"] >= 0


# ── regressions found while running live ────────────────────────────────────

def test_heatmap_normalises_sequence_id_timestamps():
    """Bybit's update id is not a clock — bucketing by it broke the heatmap."""
    from orderflow_system.atlas.depthmap import DepthHeatmap
    from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot

    hm = DepthHeatmap("T", tick_size=1.0, bucket_ms=1000)
    for seq in range(50):                      # 50 updates, timestamp = sequence id
        hm.on_orderbook(OrderbookSnapshot(
            timestamp_ms=seq,                                    # 0..49, not epoch ms
            bids=[OrderbookLevel(price=100.0, quantity=1.0)] , asks=[OrderbookLevel(price=101.0, quantity=1.0)],
        ))
    snap = hm.snapshot()
    assert len(snap["buckets"]) == 1, "sequence ids must collapse into one time bucket"
    assert snap["buckets"][0] > 1_000_000_000_000, "bucket must be real epoch milliseconds"


def test_feed_extras_tolerates_sync_and_async_callbacks():
    """A sync callback used to return None and kill the listener mid-liquidation."""
    import asyncio as _asyncio
    from orderflow_system.atlas.feed_extras import BybitExtras

    seen = {"liq": 0, "book": 0, "block": 0}

    def sync_liq(**kw):
        seen["liq"] += 1

    def sync_book(*args):
        seen["book"] += 1

    def sync_block(**kw):
        seen["block"] += 1

    feed = BybitExtras("X", on_liquidation=sync_liq, on_orderbook=sync_book, on_block_trade=sync_block)
    msgs = [
        {"topic": "allLiquidation.X", "ts": T0, "data": [{"T": T0, "s": "X", "S": "Sell", "v": "1", "p": "100"}]},
        {"topic": "orderbook.200.X", "type": "snapshot", "ts": T0, "data": {"b": [["100", "1"]], "a": [["101", "1"]]}},
        {"topic": "publicTrade.X", "ts": T0, "data": [{"T": T0, "p": "100", "v": "2", "S": "Buy", "BT": True}]},
        {"success": False, "ret_msg": "error:handler not found,topic:publicTrade.NOPE", "op": "subscribe"},
    ]
    for m in msgs:
        _asyncio.run(feed._handle(m))          # must not raise

    assert seen == {"liq": 1, "book": 1, "block": 1}
    assert feed.stats["liquidations"] == 1 and feed.stats["block_trades"] == 1


def test_the_primary_book_never_double_paints_a_live_extras_book():
    """§131: ONE book per symbol. The deep extras book supersedes the primary's where it is fresh,
    and the primary resumes the moment the extras socket dies — a stale map is worse than a
    shallow one, but two books under one heatmap is worse than either."""
    from orderflow_system.atlas.hub import FeatureHub
    from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot

    class FakeExtras:
        def __init__(self, age_ms):
            self._age = age_ms

        def book_age_ms(self, symbol):
            return self._age

        def stats_for(self, symbol=None):
            return {}

    hub = FeatureHub()
    snap = OrderbookSnapshot(timestamp_ms=T0, bids=[OrderbookLevel(price=100.0, quantity=1.0)], asks=[])
    before = hub.counters["orderbooks"]

    hub._feeds["X"] = FakeExtras(1_000)                 # a live extras book for X
    hub.on_orderbook("X", snap)
    assert hub.counters["orderbooks"] == before, "the primary book must not paint over a fresh deep book"
    assert hub.counters.get("orderbooks_primary_skipped") == 1

    hub._feeds["X"] = FakeExtras(10 ** 6)               # the extras socket has gone quiet
    hub.on_orderbook("X", snap)
    assert hub.counters["orderbooks"] == before + 1, "with the extras stale the primary book resumes"

    hub.on_orderbook("Z", snap)                          # Z has no extras at all
    assert hub.counters["orderbooks"] == before + 2


def test_the_extras_book_feeds_every_consumer_once():
    """The deep book goes through the same funnel as the primary's — heatmap AND the intent and
    refill detectors — counted once, not once per connection."""
    import asyncio as _asyncio
    from orderflow_system.atlas.hub import FeatureHub

    hub = FeatureHub()
    calls: list = []
    feats = hub.ensure("X")
    feats.heatmap.on_orderbook = lambda snap: (calls.append(("heatmap", len(snap.bids))), [])[1]
    feats.intent.on_orderbook = lambda snap: (calls.append(("intent", len(snap.bids))), {})[1]
    feats.detector.on_orderbook = lambda snap: (calls.append(("detector", len(snap.bids))), {})[1]
    n0 = hub.counters["orderbooks"]

    _asyncio.run(hub._on_ext_orderbook("X", "snapshot", {"b": [["100", "2"]], "a": [["101", "3"]]}, T0))

    assert calls == [("heatmap", 1), ("intent", 1), ("detector", 1)], (
        "every book consumer reads the deep book, and each exactly once")
    assert hub.counters["orderbooks"] == n0 + 1, "one book update, one count"


def test_extras_subscribes_every_topic_on_connect(monkeypatch):
    """§131: the subscribe must ride the connection. A session built without its connect hook opens
    a socket that never subscribes — the venue answers pings so it looks alive, and no error is
    ever raised while zero market data arrives (measured live: 2 frames in 25 s, no book updates)."""
    import asyncio as _asyncio
    import json as _json

    from orderflow_system.atlas import feed_extras
    from orderflow_system.atlas.feed_extras import BybitExtras

    sent: list = []

    class FakeConn:
        async def send(self, payload):
            sent.append(payload)

        async def close(self):
            return None

        def __aiter__(self):
            async def gen():
                while True:
                    await _asyncio.sleep(0.02)
                    yield '{"topic":"orderbook.200.AAA","type":"delta","ts":1,"data":{"b":[["1","1"]],"a":[]}}'
            return gen()

    async def fake_connect(url, **kw):
        return FakeConn()

    monkeypatch.setattr(feed_extras.websockets, "connect", fake_connect)

    feed = BybitExtras(["AAA", "BBB"], on_liquidation=lambda **k: None,
                       on_orderbook=lambda *a, **k: None, on_block_trade=lambda **k: None)

    async def drive():
        task = _asyncio.create_task(feed.start())
        for _ in range(80):
            if any('"op": "subscribe"' in s or '"op":"subscribe"' in s for s in sent):
                break
            await _asyncio.sleep(0.05)
        await feed.stop()
        task.cancel()
        try:
            await task
        except _asyncio.CancelledError:
            pass

    _asyncio.run(drive())
    subs = [_json.loads(s) for s in sent if "subscribe" in s]
    assert subs, "the extras session never subscribed — `on_connected` must be passed to FeedSession"
    assert subs[0]["args"] == [
        "allLiquidation.AAA", "orderbook.200.AAA", "publicTrade.AAA",
        "allLiquidation.BBB", "orderbook.200.BBB", "publicTrade.BBB",
    ], subs[0]["args"]
    assert feed.stats["book_updates"] >= 1, "frames arriving through the session must reach routing"


def test_extras_routes_frames_by_their_own_symbol():
    """§131: one connection, many symbols — a frame reaches its own symbol's callbacks ONLY."""
    import asyncio as _asyncio
    from orderflow_system.atlas.feed_extras import BybitExtras

    seen: list[tuple] = []
    feed = BybitExtras(
        ["AAA", "BBB"],
        on_liquidation=lambda **kw: seen.append(("liq", kw["symbol"], kw["price"])),
        on_orderbook=lambda sym, typ, data, ts: seen.append(("book", sym, typ)),
        on_block_trade=lambda **kw: seen.append(("block", kw["symbol"], kw["size"])),
    )
    msgs = [
        {"topic": "orderbook.200.BBB", "type": "delta", "ts": T0, "data": {"b": [["1", "2"]], "a": []}},
        {"topic": "publicTrade.AAA", "ts": T0, "data": [{"T": T0, "p": "5", "v": "3", "S": "Buy", "BT": True}]},
        {"topic": "allLiquidation.AAA", "ts": T0, "data": [{"T": T0, "S": "Sell", "v": "2", "p": "4"}]},
        {"topic": "orderbook.200.ZZZ", "type": "delta", "ts": T0, "data": {"b": [["1", "1"]], "a": []}},
        {"op": "pong", "success": True},
    ]
    results = [_asyncio.run(feed._handle(m)) for m in msgs]

    assert seen == [("book", "BBB", "delta"), ("block", "AAA", 3.0), ("liq", "AAA", 4.0)], (
        "each frame goes to its own symbol's callback — never to another instrument's")
    assert results[:3] == [True, True, True], "parsed market data resets the reconnect ladder"
    assert results[3:] == [False, False], (
        "another symbol's topic and a pong are not data — the ladder must keep escalating")
    assert feed.stats_for("AAA")["block_trades"] == 1 and feed.stats_for("BBB")["book_updates"] == 1
    assert feed.stats["liquidations"] == 1


def test_extras_start_one_connection_for_many_symbols(monkeypatch):
    """§131: a multi-symbol start opens ONE extras connection, and stops it once."""
    import asyncio as _asyncio
    from orderflow_system.atlas import feed_extras
    from orderflow_system.atlas.hub import FeatureHub  # NB: the package's `hub` name is an INSTANCE

    made: list[list[str]] = []

    class StubFeed:
        def __init__(self, symbols, **kw):
            made.append(list(symbols) if isinstance(symbols, list) else [symbols])
            self.stats: dict = {}

        async def start(self):
            return None

        async def stop(self):
            return None

        def stats_for(self, symbol=None):
            return {}

    monkeypatch.setattr(feed_extras, "BybitExtras", StubFeed)
    h = FeatureHub()
    h.extras_enabled = True

    result = _asyncio.run(h.start_feeds({"BTCUSDT": 0.1, "ETHUSDT": 0.01, "SOLUSDT": 0.001}))
    assert len(made) == 1, "five instruments used to mean five sockets; one connection carries them all"
    assert made[0] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert result["feeds"] == 1 and result["symbols"] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert _asyncio.run(h.stop_feeds())["ok"] is True


def test_liquidation_routes_into_hub_and_tracker():
    hub = FeatureHub()
    hub.on_liquidation("X", price=100.0, size=5.0, side="Sell", ts_ms=T0)
    assert hub.counters["liquidations"] == 1
    liqs = hub.snapshot_tape("X")["events"]["liquidations"]
    assert len(liqs) == 1 and liqs[0]["price"] == 100.0


def test_replay_can_be_replayed_after_finishing(tmp_path):
    """Scrubbing a finished session must arm it again, not leave it stuck."""
    db = str(tmp_path / "replay4.db")
    _make_db(db, [("X", T0 + i * 10, 50.0 + i, 1.0, "buy") for i in range(40)])
    replay = MarketReplay(db, speed=1000.0, max_gap_ms=0)

    async def run() -> dict:
        await replay.load("X")
        seen = []

        async def collect(t):
            seen.append(t)

        await replay.play(collect)
        await replay._task
        finished = replay.status()["state"]

        replay.seek_fraction(0.5)                    # scrub back to the middle
        armed = replay.status()
        seen.clear()
        await replay.play(collect)
        await replay._task
        return {
            "finished": finished,
            "state_after_seek": armed["state"],
            "index_after_seek": armed["index"],
            "replayed": len(seen),
            "final": replay.status()["state"],
        }

    out = asyncio.run(run())
    assert out["finished"] == "finished"
    assert out["state_after_seek"] == "loaded"
    assert out["index_after_seek"] == 20
    assert out["replayed"] == 20                     # only the back half was replayed
    assert out["final"] == "finished"


# ── the reference layout parity: alert webhook + CSV export ─────────────────────────────────

def test_webhook_posts_only_opted_in_rules(monkeypatch):
    """Rules with a 'webhook' channel POST; others stay local."""
    import asyncio as _a
    from orderflow_system.atlas.alerts import AlertEngine

    engine = AlertEngine([
        {"id": "with", "name": "with hook", "kind": "big_trade", "cooldown_s": 0,
         "channels": ["webhook"], "params": {"min_multiple": 1.0}},
        {"id": "without", "name": "no hook", "kind": "big_trade", "cooldown_s": 0,
         "channels": ["ui"], "params": {"min_multiple": 1.0}},
    ], webhook_url="http://127.0.0.1:9/never")

    posted: list[dict] = []

    class FakeResp:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakeSession:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def post(self, url, json=None):
            posted.append({"url": url, "json": json})
            return FakeResp()

    import sys
    import types

    fake_aiohttp = types.ModuleType("aiohttp")
    fake_aiohttp.ClientTimeout = lambda total=None: None          # type: ignore[attr-defined]
    fake_aiohttp.ClientSession = FakeSession                      # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)

    fired = engine.evaluate("X", "big_trade", {"multiple": 2.0, "side": "buy", "price": 1, "size": 1, "ts_ms": 1})
    assert len(fired) == 2, "both rules fire locally"
    sent = _a.run(engine.dispatch_webhooks(fired))
    assert sent == 1, "only the webhook-channel rule is forwarded"
    assert len(posted) == 1 and posted[0]["json"]["rule_id"] == "with"
    assert posted[0]["json"]["type"] == "orderflow_alert"
    assert engine.webhook_stats["sent"] == 1


def test_webhook_failure_is_counted_not_raised(monkeypatch):
    """An unreachable webhook must never affect the pipeline."""
    import asyncio as _a
    from orderflow_system.atlas.alerts import AlertEngine

    engine = AlertEngine([{"id": "w", "name": "w", "kind": "big_trade", "cooldown_s": 0,
                           "channels": ["webhook"], "params": {}}], webhook_url="http://127.0.0.1:9/x")

    class BoomSession:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def post(self, url, json=None):
            raise OSError("connection refused")

    import sys
    import types

    fake = types.ModuleType("aiohttp")
    fake.ClientTimeout = lambda total=None: None                      # type: ignore[attr-defined]
    fake.ClientSession = BoomSession                                  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiohttp", fake)

    fired = engine.evaluate("X", "big_trade", {"multiple": 1.0, "side": "buy", "price": 1, "size": 1, "ts_ms": 1})
    sent = _a.run(engine.dispatch_webhooks(fired))
    assert sent == 0
    assert engine.webhook_stats["failed"] == 1
    assert "OSError" in engine.webhook_stats["last_error"]


def test_csv_exports_are_well_formed(tmp_path):
    """Alert log and tape CSV exports carry the expected columns."""
    import csv as _csv
    import io as _io

    from orderflow_system.atlas.hub import FeatureHub
    from orderflow_system.test_atlas_integration import tick  # reuse the synthetic tick helper

    hub = FeatureHub({"tape": {"big_quantile": 0.5, "sweep_levels": 2, "sweep_max_ms": 5000},
                      "alert_rules": []})
    for i in range(60):                                       # clear the 50-print warm-up
        hub.on_tick("CSV", tick(T0 + i * 100, 100.0 + i * 0.01, 1.0))
    hub.on_tick("CSV", tick(T0 + 6100, 103.0, 50.0))          # elephant print

    alerts = list(_csv.reader(_io.StringIO(hub.alerts.to_csv())))
    assert alerts[0] == ["ts_ms", "time", "severity", "kind", "symbol", "rule", "message"]
    tape = list(_csv.reader(_io.StringIO(hub.tape_csv("CSV"))))
    assert tape[0] == ["ts_ms", "time", "kind", "price", "size", "detail"]
    assert len(tape) > 1, "the elephant print should produce export rows"
    kinds = {r[2] for r in tape[1:]}
    assert "big_trade" in kinds
    hm = list(_csv.reader(_io.StringIO(hub.heatmap_csv("CSV", columns=10, rows=5))))
    assert hm[0][0] == "price" and len(hm) >= 2


def test_rule_partial_update_merges_instead_of_resetting():
    """POSTing {'id': X, 'channels': [...]} must patch, not replace with defaults."""
    from orderflow_system.atlas.alerts import AlertEngine

    engine = AlertEngine([{"id": "bt", "name": "big trades", "kind": "big_trade", "cooldown_s": 30,
                           "channels": ["ui"], "params": {"min_multiple": 2.5}}])
    engine.upsert({"id": "bt", "channels": ["ui", "webhook"]})
    rule = next(r for r in engine.rules if r.id == "bt")
    assert rule.kind == "big_trade", "kind must survive a partial update"
    assert rule.name == "big trades"
    assert rule.params.get("min_multiple") == 2.5, "thresholds must survive a partial update"
    assert rule.channels == ["ui", "webhook"]
    # a brand-new rule still creates cleanly
    engine.upsert({"id": "new", "name": "n", "kind": "sweep", "channels": ["ui"]})
    assert {r.id for r in engine.rules} == {"bt", "new"}


def test_the_depth_store_reports_and_bounds_its_columns():
    """R-01: the store reports its retained level count and its columns deque caps."""
    from orderflow_system.atlas.depthmap import DepthHeatmap
    from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot

    heat = DepthHeatmap("BTCUSDT", max_columns=30)
    base = 1_700_000_000_000
    for n in range(60):
        snap = OrderbookSnapshot(
            timestamp_ms=base + n * 60_000,
            bids=[OrderbookLevel(price=100.0 - i * 0.1, quantity=1.0 + i) for i in range(20)],
            asks=[OrderbookLevel(price=100.1 + i * 0.1, quantity=1.0 + i) for i in range(20)])
        heat.on_orderbook(snap, ts_ms=base + n * 60_000)

    st = heat.stats()
    assert st["columns"] <= 30, "the column deque stays at max_columns"
    assert st["retained_levels"] == sum(len(c.levels) for c in heat._columns)
    assert st["retained_levels"] > 0
