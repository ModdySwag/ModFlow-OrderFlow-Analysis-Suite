"""Tests for the second the reference layout pass: imbalance ladder, reassembly, zones,
durable history and Telegram routing.

Run:  .venv/Scripts/python.exe -m pytest orderflow_system/test_atlas_v2.py -v
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import time
from types import SimpleNamespace

import pytest

from orderflow_system.atlas.alerts import AlertEngine, AlertRule
from orderflow_system.atlas.history import EventHistory
from orderflow_system.atlas.hub import FeatureHub
from orderflow_system.atlas.imbalance import ImbalanceLadder
from orderflow_system.atlas.notify import TelegramNotifier
from orderflow_system.atlas.tapeflow import TapeFlow
from orderflow_system.data.models import Side, Tick

NOW = lambda: int(time.time() * 1000)          # noqa: E731  (window tests need wall clock)


def tick(ts: int, price: float, size: float, side: str = "buy") -> Tick:
    return Tick(timestamp_ms=ts, price=price, size=size,
                side=Side.BUY if side == "buy" else Side.SELL)


# ── imbalance ladder ────────────────────────────────────────────────────────

def test_imbalance_matches_atas_worked_example():
    """the reference layout: bid at a level vs the ask one level above; ask=30 at 350 % → bid>105."""
    imb = ImbalanceLadder("T", tick_size=1.0, rate_pct=150.0, window_ms=60_000)
    now = NOW()
    for i in range(30):                                   # ask-side prints at 101 (buyers)
        imb.on_tick(tick(now - (30 - i) * 10, 101.0, 1.0, "buy"))
    for i in range(105):                                  # bid-side prints at 100 (sellers)
        imb.on_tick(tick(now - (105 - i) * 5, 100.0, 1.0, "sell"))

    levels = {l["price"]: l for l in imb.snapshot()["levels"]}
    assert 100.0 in levels, "the 105/30 ratio is 350 %, well past the 150 % default"
    assert levels[100.0]["side"] == "bid"
    assert levels[100.0]["ratio_pct"] == pytest.approx(350.0, abs=0.1)

    strict = ImbalanceLadder("T", tick_size=1.0, rate_pct=400.0, window_ms=60_000)
    for i in range(30):
        strict.on_tick(tick(now - (30 - i) * 10, 101.0, 1.0, "buy"))
    for i in range(105):
        strict.on_tick(tick(now - (105 - i) * 5, 100.0, 1.0, "sell"))
    assert strict.snapshot()["levels"] == [], "350 % must not pass a 400 % rate"


def test_imbalance_ask_side_mirror_rule():
    """The mirrored reading: ask at a level vs the bid one level BELOW."""
    imb = ImbalanceLadder("T", tick_size=1.0, rate_pct=150.0, window_ms=60_000)
    now = NOW()
    for i in range(20):                                   # bid volume at 100
        imb.on_tick(tick(now - (20 - i) * 10, 100.0, 1.0, "sell"))
    for i in range(60):                                   # ask volume at 101 → 300 %
        imb.on_tick(tick(now - (60 - i) * 5, 101.0, 1.0, "buy"))

    levels = {l["price"]: l for l in imb.snapshot()["levels"]}
    assert levels[101.0]["side"] == "ask"
    assert levels[101.0]["ratio_pct"] == pytest.approx(300.0, abs=0.1)


def test_imbalance_stacks_consecutive_levels():
    imb = ImbalanceLadder("T", tick_size=1.0, rate_pct=150.0, window_ms=60_000)
    now = NOW()
    for price in (100.0, 101.0, 102.0):                   # three defended bids in a row
        for i in range(90):
            imb.on_tick(tick(now - (i + 1) * 4, price, 1.0, "sell"))
    for price in (101.0, 102.0, 103.0):                   # the asks above each level
        for i in range(20):
            imb.on_tick(tick(now - (i + 1) * 6, price, 1.0, "buy"))

    snap = imb.snapshot()
    assert snap["counts"]["bid"] >= 3
    stacked = [c for c in snap["stacked"] if c["side"] == "bid"]
    assert stacked, "three adjacent bid imbalances must form a stacked cluster"
    assert stacked[0]["levels"] >= 3
    assert stacked[0]["from_price"] == 100.0 and stacked[0]["to_price"] == 102.0


def test_imbalance_uses_the_printed_price_grid_not_the_configured_tick():
    """BTCUSDT prints on a 0.1 grid while the repo's tick_size is 0.01.

    Adjacency must come from the populated levels, not from ``price + tick`` —
    otherwise no level is ever compared and the ladder stays empty (the live
    defect this test pins).
    """
    imb = ImbalanceLadder("BTCUSDT", tick_size=0.01, rate_pct=150.0, window_ms=60_000)
    now = NOW()
    for i in range(30):                                    # ask volume one print above
        imb.on_tick(tick(now - (30 - i) * 10, 78415.1, 1.0, "buy"))
    for i in range(105):                                   # sellers absorbed at 78415.0
        imb.on_tick(tick(now - (105 - i) * 5, 78415.0, 1.0, "sell"))

    levels = {l["price"]: l for l in imb.snapshot()["levels"]}
    assert 78415.0 in levels, "the 0.1 price grid must still produce an imbalance"
    assert levels[78415.0]["side"] == "bid"
    assert levels[78415.0]["ratio_pct"] == pytest.approx(350.0, abs=0.1)


def test_imbalance_volume_floor_filters_noise_levels():
    """A single tiny print next to a big one must not report a 17 000 % ratio."""
    imb = ImbalanceLadder("T", tick_size=1.0, rate_pct=150.0, window_ms=60_000, min_volume=1.0)
    now = NOW()
    imb.on_tick(tick(now, 101.0, 10.0, "buy"))          # the "other side" volume
    imb.on_tick(tick(now + 1, 100.0, 0.5, "sell"))      # below the floor → not compared
    assert imb.snapshot()["levels"] == []
    imb.on_tick(tick(now + 2, 100.0, 4.0, "sell"))      # 4.5 vs 10 = 45 % on the bid side…
    mid = imb.snapshot()["levels"]                       # …but the mirror now reads ask@101 vs bid@100
    assert len(mid) == 1 and mid[0]["side"] == "ask" and mid[0]["price"] == 101.0
    imb.on_tick(tick(now + 3, 100.0, 20.0, "sell"))     # 24.5 vs 10 = 245 % → bid level fires
    lv = imb.snapshot()["levels"]
    assert len(lv) == 1 and lv[0]["side"] == "bid" and lv[0]["price"] == 100.0
    assert lv[0]["ratio_pct"] == pytest.approx(245.0, abs=0.1)


def test_imbalance_window_expiry_drops_old_prints():
    imb = ImbalanceLadder("T", tick_size=1.0, rate_pct=150.0, window_ms=1_000)
    now = NOW()
    for i in range(105):
        imb.on_tick(tick(now - 60_000 - i * 5, 100.0, 1.0, "sell"))   # ancient
    for i in range(30):
        imb.on_tick(tick(now - i * 5, 101.0, 1.0, "buy"))
    assert imb.snapshot()["levels"] == [], "prints older than the window must not count"


def test_imbalance_alert_fires_once_for_a_cluster():
    """The hub-level detection only reports a fresh, tall-enough cluster."""
    imb = ImbalanceLadder("T", tick_size=1.0, rate_pct=150.0, window_ms=60_000,
                          alert_min_levels=3, poll_interval_ms=0)
    now = NOW()
    fired = 0
    for round_ in range(2):                               # same picture twice
        for price in (100.0, 101.0, 102.0):
            for i in range(90):
                out = imb.on_tick(tick(now + round_ * 100 + i, price, 1.0, "sell"))
                if "stacked_imbalance" in out:
                    fired += 1
        for price in (101.0, 102.0, 103.0):
            for i in range(20):
                out = imb.on_tick(tick(now + round_ * 100 + i, price, 1.0, "buy"))
                if "stacked_imbalance" in out:
                    fired += 1
    assert fired == 1, f"an unchanged picture must not re-fire (fired {fired}x)"


# ── big-trade reassembly + zones ────────────────────────────────────────────

def flow(**kw) -> TapeFlow:
    kw.setdefault("big_min_size", 10.0)        # deterministic threshold (<50 samples)
    kw.setdefault("reassembly_ms", 100)
    return TapeFlow("T", tick_size=1.0, **kw)


def test_reassembly_aggregates_fragments_into_one_big_trade():
    tf = flow()
    now = NOW()
    fired = []
    for i, size in enumerate((3.0, 4.0, 4.0)):            # 11 total > 10 threshold
        out = tf.on_tick(tick(now + i, 100.0, size, "buy"))
        fired += [v for k, v in out.items() if k == "big_trade"]

    assert len(fired) == 1, "one aggregate, not one per fragment"
    bt = fired[0]
    assert bt.reassembled is True and bt.fragments == 3
    assert bt.size == pytest.approx(11.0)
    assert tf.stats()["big_trades"] == 1
    assert tf.stats()["reassembled"] == 1


def test_reassembly_ignores_opposite_side_and_other_prices():
    tf = flow()
    now = NOW()
    for i, (price, side) in enumerate(((100.0, "buy"), (100.0, "sell"), (101.0, "buy"))):
        out = tf.on_tick(tick(now + i, price, 4.0, side))
        assert "big_trade" not in out, "no run of same-side same-price prints yet"
    assert tf.stats()["big_trades"] == 0


def test_reassembly_does_not_repeat_for_an_unchanged_run():
    """A run reports when it crosses the threshold, then only when it doubles."""
    tf = flow()
    now = NOW()
    first = tf.on_tick(tick(now, 100.0, 6.0, "buy"))            # 6 < 10 → nothing
    second = tf.on_tick(tick(now + 1, 100.0, 6.0, "buy"))       # 12 > 10 → fires
    third = tf.on_tick(tick(now + 2, 100.0, 1.0, "buy"))        # 13 → too small a change
    fourth = tf.on_tick(tick(now + 3, 100.0, 12.0, "buy"))      # 25 ≥ 2×12 → fires again
    assert "big_trade" not in first
    assert "big_trade" in second
    assert "big_trade" not in third, "a 1-unit drip must not re-alert"
    assert "big_trade" in fourth, "a doubling is news"
    assert tf.stats()["big_trades"] == 2


def test_single_large_print_still_reports_as_before():
    tf = flow()
    out = tf.on_tick(tick(NOW(), 100.0, 25.0, "buy"))
    bt = out["big_trade"]
    assert bt.reassembled is False and bt.fragments == 1


def test_zones_aggregate_big_trades_by_price_bin():
    tf = flow(zone_ticks=100.0)
    now = NOW()
    tf.on_tick(tick(now, 150.0, 30.0, "buy"))             # zone base 100
    tf.on_tick(tick(now + 1, 149.0, 20.0, "sell"))        # same zone
    tf.on_tick(tick(now + 2, 260.0, 12.0, "buy"))         # zone base 300
    zones = tf.zones()
    assert len(zones) == 2
    assert zones[0]["zone_price"] == 100.0                # biggest volume first
    assert zones[0]["total"] == pytest.approx(50.0)
    assert zones[0]["delta"] == pytest.approx(10.0)
    assert zones[0]["count"] == 2


# ── durable history ─────────────────────────────────────────────────────────

def test_history_roundtrip(tmp_path):
    db = str(tmp_path / "hist.db")
    hist = EventHistory(db)

    async def run() -> dict:
        hist.record("BTCUSDT", "big_trade", price=100.0, size=3.0, detail="x")
        hist.record("BTCUSDT", "alert", price=100.0, size=3.0, detail="big trade alert")
        hist.record("ETHUSDT", "sweep", price=50.0, size=1.0)
        written = await hist.flush()
        return {
            "written": written,
            "btc": await asyncio.to_thread(hist.recent, "BTCUSDT"),
            "counts": await asyncio.to_thread(hist.counts, "BTCUSDT"),
            "total": await asyncio.to_thread(hist.total),
        }

    out = asyncio.run(run())
    assert out["written"] == 3
    assert len(out["btc"]) == 2 and out["btc"][0]["kind"] == "alert"   # newest first
    assert out["counts"] == {"big_trade": 1, "alert": 1}
    assert out["total"] == 3


def test_history_disabled_writes_nothing(tmp_path):
    db = str(tmp_path / "off.db")
    hist = EventHistory(db, enabled=False)
    hist.record("BTCUSDT", "sweep")
    asyncio.run(hist.flush())
    con = sqlite3.connect(db)
    try:
        tables = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    finally:
        con.close()
    assert tables == [], "disabled history must not even create the table"


# ── Telegram routing ────────────────────────────────────────────────────────

def test_notifier_throttles_bursts_and_formats_plain_text():
    sent: list[str] = []

    async def transport(text: str) -> bool:
        sent.append(text)
        return True

    notifier = TelegramNotifier(enabled=True, transport=transport, min_interval_s=60.0)

    async def run() -> tuple[bool, bool]:
        await notifier.start()
        first = await notifier.send({"symbol": "BTCUSDT", "kind": "stop_run", "severity": "critical",
                                     "message": "stop run down", "name": "Stop run", "ts_ms": NOW()})
        second = await notifier.send({"symbol": "BTCUSDT", "kind": "sweep", "severity": "warning",
                                      "message": "sweep", "name": "Sweep", "ts_ms": NOW()})
        return first, second

    first, second = asyncio.run(run())
    assert first is True and second is False, "the burst throttle must hold the second message"
    assert notifier.sent == 1 and notifier.throttled == 1
    assert "BTCUSDT" in sent[0] and "STOP RUN" in sent[0]


def test_hub_routes_only_alerts_with_an_external_channel():
    """The rule's channels decide routing; the hub records every detection.

    Guards the ntfy-only case too: the dispatch gate must not look for the word
    "telegram" specifically, or a user whose only channel is ntfy/email gets
    silence with no error anywhere.
    """
    sent: list[str] = []

    async def transport(text: str) -> bool:
        sent.append(text)
        return True

    class FakeHistory:
        def __init__(self) -> None:
            self.rows: list[tuple] = []
            self.enabled = True
            self.written = 0
            self.pending = 0

        def record(self, symbol, kind, price=0.0, size=0.0, detail="", ts_ms=None):
            self.rows.append((symbol, kind, price, size, detail))

    hub = FeatureHub({"tape": {"big_min_size": 1.0}, "alert_rules": [
        {"id": "bt", "name": "Big trade", "kind": "big_trade", "enabled": True,
         "params": {"min_multiple": 1.5}, "cooldown_s": 0, "channels": ["ui", "ntfy"]},
        {"id": "sw", "name": "Sweep", "kind": "sweep", "enabled": True,
         "params": {}, "cooldown_s": 0, "channels": ["ui"]},
    ]})
    hist = FakeHistory()
    hub.attach_history(hist)
    notifier = TelegramNotifier(enabled=True, transport=transport, min_interval_s=0.0)
    hub.attach_notifier(notifier)

    async def run() -> None:
        await notifier.start()
        hub.on_tick("BTCUSDT", tick(NOW(), 100.0, 3.0, "buy"))     # big trade → alert → external
        await asyncio.sleep(0.05)
        # a sweep-shaped detection on a ui-only rule must NOT leave the app
        hub._dispatch("BTCUSDT", "sweep", {"ts_ms": NOW(), "side": "buy", "levels": 6,
                                           "size": 5.0, "from_price": 100.0, "to_price": 101.0,
                                           "duration_ms": 40})
        await asyncio.sleep(0.05)

    asyncio.run(run())
    kinds = [r[1] for r in hist.rows]
    assert "big_trade" in kinds and "alert" in kinds and "sweep" in kinds
    assert len(sent) == 1, f"only the externally-routed rule may send (sent {len(sent)})"
    assert "BIG TRADE" in sent[0]


def test_alert_carries_rule_channels():
    engine = AlertEngine([{"id": "x", "name": "Stop run", "kind": "stop_run", "enabled": True,
                           "params": {"min_ticks": 5}, "cooldown_s": 0,
                           "channels": ["ui", "telegram"]}])
    fired = engine.evaluate("BTCUSDT", "stop_run", {"ts_ms": NOW(), "direction": "down", "ticks_moved": 9})
    assert len(fired) == 1
    assert fired[0].channels == ["ui", "telegram"]
    assert fired[0].to_dict()["channels"] == ["ui", "telegram"]


def test_default_rules_include_the_stacked_imbalance_rule():
    rules = {r.id: r for r in AlertEngine().rules}
    assert "stacked-imb" in rules
    assert rules["stacked-imb"].kind == "stacked_imbalance"
    assert "telegram" in rules["stacked-imb"].channels
    assert AlertRule.from_dict({"id": "a", "kind": "b"}).channels == ["ui"]


# ═══════════════════════════════════════════════════════════════
# Free integrations: ntfy push, email, notifier routing, market context
# ═══════════════════════════════════════════════════════════════

def test_ntfy_formats_for_a_lock_screen():
    from orderflow_system.atlas.notify import NtfyNotifier

    sent = []

    async def transport(url, headers, body):
        sent.append((url, headers, body))
        return True

    n = NtfyNotifier(server="https://ntfy.sh", topic="my-topic", transport=transport)
    assert asyncio.run(n.start()) is True
    ok = asyncio.run(n.send({"symbol": "btcusdt", "kind": "stop_run", "severity": "critical",
                             "message": "Stop run through 78,400", "name": "Stops"}, force=True))
    assert ok is True
    url, headers, body = sent[0]
    assert url == "https://ntfy.sh/my-topic"
    assert headers["Title"] == "BTCUSDT · STOP RUN"
    assert headers["Priority"] == "urgent" and headers["Tags"] == "rotating_light"
    assert "Stop run through" in body


def test_ntfy_needs_no_credentials_but_requires_a_topic():
    from orderflow_system.atlas.notify import NtfyNotifier

    blank = NtfyNotifier(topic="")
    assert asyncio.run(blank.start()) is False      # nothing configured → inert, never raises
    assert blank.stats()["ready"] is False

    # a bare host is normalised and the URL is built correctly
    n = NtfyNotifier(server="ntfy.example.com", topic="/ops/", transport=lambda *a: None)
    assert n.url == "https://ntfy.example.com/ops"


def test_email_formats_and_uses_the_injected_transport():
    from orderflow_system.atlas.notify import EmailNotifier

    outbox = []

    async def transport(subject, body):
        outbox.append((subject, body))
        return True

    n = EmailNotifier(host="smtp.example.com", username="me@example.com", to_addrs="a@x.com, b@y.com",
                      transport=transport)
    assert asyncio.run(n.start()) is True
    assert n.to_addrs == ["a@x.com", "b@y.com"]
    ok = asyncio.run(n.send({"symbol": "ETHUSDT", "kind": "big_trade", "severity": "warning",
                             "message": "Big sell 250 ETH", "price": 2500.0}, force=True))
    assert ok is True
    subject, body = outbox[0]
    assert subject.startswith("[OrderFlow] WARNING · ETHUSDT · big trade")
    assert "Big sell 250 ETH" in body and "severity:warning" in body


def test_email_is_inert_without_host_and_recipient():
    from orderflow_system.atlas.notify import EmailNotifier

    n = EmailNotifier(host="", to_addrs="")
    assert asyncio.run(n.start()) is False
    assert asyncio.run(n.send({"symbol": "X"}, force=True)) is False


def test_notifier_hub_routes_only_the_channels_the_rule_asked_for():
    from orderflow_system.atlas.notify import NotifierHub

    calls = {"tg": 0, "ntfy": 0, "mail": 0}

    class Fake:
        def __init__(self, key):
            self.key = key

        async def start(self):
            return True

        async def stop(self):
            pass

        async def send(self, alert, force=False):
            calls[self.key] += 1
            return True

        def stats(self):
            return {"sent": calls[self.key]}

    hub = NotifierHub(telegram=Fake("tg"), ntfy=Fake("ntfy"), email=Fake("mail"))
    out = asyncio.run(hub.send({"symbol": "BTCUSDT", "channels": ["ui", "ntfy", "email"]}))
    assert set(out) == {"ntfy", "email"} and calls == {"tg": 0, "ntfy": 1, "mail": 1}
    assert hub.routing({"channels": ["webhook"]}) == []          # unknown channel → nothing


def test_notifier_hub_reports_an_unconfigured_channel():
    from orderflow_system.atlas.notify import NotifierHub

    hub = NotifierHub()
    r = asyncio.run(hub.send_one("ntfy", {"symbol": "BTCUSDT"}))
    assert r["ok"] is False and "not configured" in r["error"]


def test_build_notifiers_only_builds_configured_channels():
    from orderflow_system.atlas.notify import build_notifiers

    empty = build_notifiers()
    assert empty.channels == {}                                   # fresh install: UI-only, no errors

    full = build_notifiers(
        telegram_cfg={"bot_token": "123:abc", "chat_id": "42", "enabled": True},
        notify_cfg={"ntfy": {"enabled": True, "topic": "t1"},
                    "email": {"enabled": True, "host": "smtp.x.com", "to": "a@b.c"}},
    )
    assert sorted(full.channels) == ["email", "ntfy", "telegram"]


def test_parse_rss_handles_rss_and_atom():
    from orderflow_system.atlas.context import parse_rss

    rss = """<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>Bitcoin holds 78k</title><link>https://example.com/a</link>
        <pubDate>Mon, 15 Sep 2026 00:05:00 +0000</pubDate></item>
      <item><title>Second story</title><link>https://example.com/b</link></item>
    </channel></rss>"""
    items = parse_rss(rss, source="example.com")
    assert [i["title"] for i in items] == ["Bitcoin holds 78k", "Second story"]
    assert items[0]["link"] == "https://example.com/a" and items[0]["source"] == "example.com"

    atom = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Atom entry</title><link href="https://example.com/c"/>
        <updated>2026-09-15T00:10:00Z</updated></entry></feed>"""
    atom_items = parse_rss(atom, source="atom.example")
    assert atom_items and atom_items[0]["title"] == "Atom entry" and atom_items[0]["link"] == "https://example.com/c"


def test_market_context_caches_and_survives_a_dead_source(monkeypatch):
    from orderflow_system.atlas import context as ctx_mod

    calls = {"news": 0, "venue": 0}

    def fake_fetch_text(url, timeout_s=8.0):
        calls["news"] += 1
        if "dead" in url:
            raise OSError("connection refused")
        return "<rss><channel><item><title>Live headline</title><link>https://x/1</link></item></channel></rss>"

    def fake_fetch_json(url, timeout_s=8.0):
        calls["venue"] += 1
        if "account-ratio" in url:
            raise OSError("ratio endpoint down")
        return {"result": {"list": [{"lastPrice": "78000", "fundingRate": "0.0001",
                                     "nextFundingTime": "1789000000000", "openInterest": "12345",
                                     "openInterestValue": "9.6e8", "price24hPcnt": "0.012",
                                     "turnover24h": "1.2e9", "volume24h": "15000"}]}}

    monkeypatch.setattr(ctx_mod, "_fetch_text", fake_fetch_text)
    monkeypatch.setattr(ctx_mod, "_fetch_json", fake_fetch_json)

    mc = ctx_mod.MarketContext(news_feeds=("https://good.example/rss", "https://dead.example/rss"))
    pos = mc.positioning("BTCUSDT")
    assert pos["ok"] is True and pos["funding_pct"] == pytest.approx(0.01)
    assert "long_short_ratio" not in pos                     # dead ratio degrades alone, no raise

    news = mc.news(limit=5)
    assert [n["title"] for n in news] == ["Live headline"]   # dead feed skipped, live one kept

    before = calls["news"]
    mc.news(limit=5)                                         # second call inside the TTL → cache
    assert calls["news"] == before

    snap = asyncio.run(mc.snapshot("BTCUSDT"))
    assert snap["ok"] is True and snap["symbol"] == "BTCUSDT"
    assert snap["positioning"]["ok"] and snap["news"]
    assert mc.stats()["requests"] >= 2


# ═══════════════════════════════════════════════════════════════
# Participants' intent — order-book reading (the reference layout DOM Pressure model)
# ═══════════════════════════════════════════════════════════════

def _book(ts: int, bid_sizes: list[float], ask_sizes: list[float],
          bid0: float = 100.0, tick: float = 0.1):
    from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot
    bids = [OrderbookLevel(price=round(bid0 - i * tick, 4), quantity=s) for i, s in enumerate(bid_sizes)]
    asks = [OrderbookLevel(price=round(bid0 + tick + i * tick, 4), quantity=s) for i, s in enumerate(ask_sizes)]
    return OrderbookSnapshot(timestamp_ms=ts, bids=bids, asks=asks)


def test_dom_pressure_uses_the_documented_exponential_decay():
    """weight = e^(-level/decay); the weighted totals must match hand maths."""
    import math as _m

    from orderflow_system.atlas.intent import ParticipantIntent

    ts = NOW()
    pi = ParticipantIntent("T", tick_size=0.1, levels=10, decay=3.0, training_s=0)
    pi.on_orderbook(_book(ts, [5.0] * 10, [5.0] * 10))
    balanced = pi.pressure()
    assert balanced["buy_weighted"] == pytest.approx(balanced["sell_weighted"], rel=1e-9)
    assert balanced["buy_pct_of_normal"] == pytest.approx(100.0, rel=1e-6)

    near = ParticipantIntent("T", tick_size=0.1, levels=10, decay=1.0, training_s=0)
    near.on_orderbook(_book(ts, [1.0] * 10, [1.0] * 10))
    flat = ParticipantIntent("T", tick_size=0.1, levels=10, decay=20.0, training_s=0)
    flat.on_orderbook(_book(ts, [1.0] * 10, [1.0] * 10))
    expected_near = sum(_m.exp(-k / 1.0) for k in range(1, 11))
    expected_flat = sum(_m.exp(-k / 20.0) for k in range(1, 11))
    assert near.pressure()["buy_weighted"] == pytest.approx(expected_near, rel=1e-6)
    assert flat.pressure()["buy_weighted"] == pytest.approx(expected_flat, rel=1e-6)
    assert near.pressure()["buy_weighted"] < flat.pressure()["buy_weighted"], \
        "a small decay must weight near levels much more heavily"


def test_pressure_alert_needs_training_and_a_baseline():
    """Both gates matter: the training period, and enough history for "normal" to exist."""
    from orderflow_system.atlas.intent import ParticipantIntent

    training = ParticipantIntent("T", tick_size=0.1, threshold_pct=80.0, training_s=300)
    out = training.on_orderbook(_book(NOW(), [50.0] * 5, [1.0] * 5))
    assert "intent_pressure" not in out, "no alerts while training (the reference layout contract)"
    assert training.pressure()["training"] is True

    # training skipped, but a single book update is not a baseline: the first
    # observation is always 100% of its own maximum, so it must not alert
    young = ParticipantIntent("T", tick_size=0.1, threshold_pct=80.0, training_s=0)
    assert "intent_pressure" not in young.on_orderbook(_book(NOW(), [50.0] * 5, [1.0] * 5))

    ready = ParticipantIntent("T", tick_size=0.1, threshold_pct=80.0, training_s=0)
    ready.on_orderbook(_book(NOW(), [40.0] * 5, [40.0] * 5))          # sets the sliding maximum
    for i in range(35):                                               # history: quiet book
        assert "intent_pressure" not in ready.on_orderbook(_book(NOW() + 100 * (i + 1), [1.0] * 5, [1.0] * 5))
    out2 = ready.on_orderbook(_book(NOW() + 4000, [40.0] * 5, [40.0] * 5))   # back to the maximum
    assert "intent_pressure" in out2, "a side back at its normal maximum must alert past the threshold"
    ev = out2["intent_pressure"][0]
    assert ev["side"] in ("bid", "ask") and ev["pct"] >= 80.0


def test_pulled_size_is_recorded_only_when_not_traded():
    from orderflow_system.atlas.intent import ParticipantIntent

    ts = NOW()
    pi = ParticipantIntent("T", tick_size=0.1, spoof_near_ticks=5, spoof_size_mult=2.0,
                           spoof_max_traded_pct=20.0, training_s=0)
    pi.on_orderbook(_book(ts, [1.0, 1.0, 30.0], [1.0, 1.0, 1.0]))
    out = pi.on_orderbook(_book(ts + 500, [1.0, 1.0, 0.1], [1.0, 1.0, 1.0]))
    assert "pulled_size" in out and out["pulled_size"][0].side == "bid"
    assert out["pulled_size"][0].size == pytest.approx(29.9, abs=0.2)   # peak minus what stayed

    traded = ParticipantIntent("T", tick_size=0.1, spoof_near_ticks=5, spoof_size_mult=2.0,
                               spoof_max_traded_pct=20.0, training_s=0)
    traded.on_orderbook(_book(ts, [1.0, 1.0, 30.0], [1.0, 1.0, 1.0]))
    for i in range(5):
        traded.on_tick(tick(ts + 100 + i, 99.8, 8.0, "sell"))      # 40 traded at that price
    out2 = traded.on_orderbook(_book(ts + 500, [1.0, 1.0, 0.1], [1.0, 1.0, 1.0]))
    assert "pulled_size" not in out2, "size that traded is not a pull"


def test_trapped_side_after_a_failed_break():
    from orderflow_system.atlas.intent import ParticipantIntent

    ts = NOW()
    pi = ParticipantIntent("T", tick_size=0.1, trap_ticks=3.0, trap_window_s=120,
                           trap_reclaim_s=60, training_s=0)
    for i in range(10):
        pi.on_tick(tick(ts + i * 100, 100.0 + (i % 2) * 0.1, 1.0))
    out: dict = {}
    for i in range(6):
        out = pi.on_tick(tick(ts + 1000 + i * 100, 100.5 + i * 0.1, 1.0))
    assert "trapped" not in out, "a break in progress is not a trap yet"
    for i in range(8):
        out = pi.on_tick(tick(ts + 2000 + i * 100, 100.4 - i * 0.1, 1.0))
        if "trapped" in out:
            break
    assert "trapped" in out, "a break that gets reclaimed traps the chasers"
    assert out["trapped"].side == "longs"


def test_absorption_reads_aggression_that_does_not_move_price():
    from orderflow_system.atlas.intent import ParticipantIntent

    base = int(time.time())
    pi = ParticipantIntent("T", tick_size=0.1, absorb_window_s=60, absorb_ref_ticks=8.0, training_s=0)
    pi.on_orderbook(_book(NOW(), [1.0] * 5, [1.0] * 5))
    for i in range(30):
        pi.on_tick(tick((base + i) * 1000 + 10, 100.05, 2.0, "buy"))
    a = pi.absorption()
    assert a["available"] and a["absorbing"] == "sellers" and a["aggressor"] == "buyers"
    assert a["score"] > 50

    pi2 = ParticipantIntent("T", tick_size=0.1, absorb_window_s=60, training_s=0)
    pi2.on_orderbook(_book(NOW(), [1.0] * 5, [1.0] * 5))
    for i in range(30):
        pi2.on_tick(tick((base + i) * 1000 + 20, 100.05, 2.0, "sell"))
    assert pi2.absorption()["absorbing"] == "buyers"


def test_tape_quality_classifies_prints_against_the_book():
    from orderflow_system.atlas.intent import ParticipantIntent

    pi = ParticipantIntent("T", tick_size=0.1, training_s=0)
    pi.on_orderbook(_book(NOW(), [1.0, 1.0], [1.0, 1.0], bid0=100.0))     # bid 100.0 / ask 100.1
    pi.on_tick(tick(NOW() + 1, 100.1, 1.0, "buy"))       # at ask
    pi.on_tick(tick(NOW() + 2, 100.0, 1.0, "sell"))      # at bid
    pi.on_tick(tick(NOW() + 3, 100.05, 1.0, "buy"))      # inside the spread
    pi.on_tick(tick(NOW() + 4, 100.2, 1.0, "buy"))       # above ask → slippage
    pi.on_tick(tick(NOW() + 5, 99.9, 1.0, "sell"))       # below bid → slippage
    tq = pi.tape_quality()
    assert tq["at_ask"] == 1 and tq["at_bid"] == 1 and tq["inside"] == 1
    assert tq["above_ask"] == 1 and tq["below_bid"] == 1
    assert tq["slippage_prints"] == 2 and tq["fresh_book"] is True

    # a stale book must not be used to judge prints (every fast move would read as slippage)
    stale = ParticipantIntent("T", tick_size=0.1, training_s=0)
    stale.on_orderbook(_book(NOW(), [1.0, 1.0], [1.0, 1.0], bid0=100.0))
    stale.on_tick(tick(NOW() + 5000, 100.5, 1.0, "buy"))
    assert stale.tape_quality()["stale_book"] == 1 and stale.tape_quality()["slippage_prints"] == 0


def test_intent_snapshot_is_versioned_and_cached():
    from orderflow_system.atlas.intent import ParticipantIntent

    pi = ParticipantIntent("T", tick_size=0.1, training_s=0)
    pi.on_orderbook(_book(NOW(), [2.0] * 5, [2.0] * 5))
    pi.on_tick(tick(NOW() + 1, 100.05, 1.0, "buy"))
    first = pi.snapshot()
    assert first["cached"] is False and first["version"] > 0
    again = pi.snapshot()
    assert again["cached"] is True and again["version"] == first["version"]
    pi.on_tick(tick(NOW() + 2, 100.05, 1.0, "buy"))
    assert pi.snapshot()["cached"] is False
    assert isinstance(first["verdict"]["line"], str) and first["verdict"]["line"]


def test_intent_alert_rules_fire_through_the_engine():
    engine = AlertEngine([
        {"id": "ip", "name": "Book pressure", "kind": "intent_pressure", "enabled": True,
         "params": {"min_pct": 80}, "cooldown_s": 0, "channels": ["ui"]},
        {"id": "pp", "name": "Pulled size", "kind": "pulled_size", "enabled": True,
         "params": {"min_size": 5.0, "max_distance_ticks": 10.0}, "cooldown_s": 0, "channels": ["ui"]},
        {"id": "tt", "name": "Trapped", "kind": "trapped_traders", "enabled": True,
         "params": {"min_beyond_ticks": 3.0}, "cooldown_s": 0, "channels": ["ui"]},
    ])
    fired = engine.evaluate("BTCUSDT", "intent_pressure",
                            {"ts_ms": NOW(), "side": "bid", "pct": 92.5, "threshold": 80, "price": 100.0})
    assert fired and "buy side" in fired[0].message and fired[0].severity == "warning"

    fired = engine.evaluate("BTCUSDT", "pulled_size",
                            {"ts_ms": NOW(), "size": 12.0, "side": "ask", "distance_ticks": 3.0,
                             "price": 100.5, "traded": 0.0})
    assert fired and "pulled from the ask" in fired[0].message

    fired = engine.evaluate("BTCUSDT", "trapped_traders",
                            {"ts_ms": NOW(), "side": "longs", "level": 100.8, "beyond_ticks": 4.0,
                             "reclaim_ms": 12000})
    assert fired and "longs trapped" in fired[0].message


def test_intent_normalises_second_precision_book_timestamps():
    """The extras book feed stamps seconds; the tape uses ms — must not skew."""
    from orderflow_system.atlas.intent import ParticipantIntent

    pi = ParticipantIntent("T", tick_size=0.1, training_s=0)
    ts_seconds = NOW() // 1000                       # the shape the deeper feed sends
    pi.on_orderbook(_book(ts_seconds, [1.0, 1.0], [1.0, 1.0], bid0=100.0))
    assert pi._last_book_ms > 10_000_000_000, "seconds must be normalised to ms"

    # the same feed can hand over the book's update id (≈1e8) instead of a clock
    update_id = ParticipantIntent("T", tick_size=0.1, training_s=0)
    update_id.on_orderbook(_book(147_371_520, [1.0, 1.0], [1.0, 1.0], bid0=100.0))
    assert update_id._last_book_ms > 1_577_000_000_000, "an update id is not a timestamp"
    assert update_id.stats()["book_age_ms"] < 5_000
    pi.on_tick(tick(NOW() + 100, 100.1, 1.0, "buy"))
    tq = pi.tape_quality()
    assert tq["fresh_book"] is True, "a book one update old is fresh"
    assert tq["stale_book"] == 0 and tq["at_ask"] == 1


def test_ntfy_backs_off_when_rate_limited():
    """HTTP 429 must widen the throttle, not retry into the wall."""
    from orderflow_system.atlas.notify import NtfyNotifier

    n = NtfyNotifier(topic="t", min_interval_s=1.5)
    start = n.min_interval_s
    n._note_rate_limited()
    assert n.min_interval_s == pytest.approx(start * 2) and n.rate_limited == 1
    for _ in range(20):
        n._note_rate_limited()
    assert n.min_interval_s == pytest.approx(60.0), "the back-off is capped"
    assert n.stats()["rate_limited"] == 21 and n.stats()["min_interval_s"] == 60.0


def test_absorption_scores_an_adverse_move_as_the_strongest_read():
    """Buyers pressing while price falls away = sellers absorbing, and that is the
    strongest read — an earlier formula scored it as zero."""
    from orderflow_system.atlas.intent import ParticipantIntent

    pi = ParticipantIntent("T", tick_size=0.1, training_s=0, absorb_window_s=60, absorb_ref_ticks=8)
    t = NOW()
    for i in range(60):
        pi.on_tick(tick(t + i * 100, 100.0 - i * 0.02, 25.0, "buy"))
    a = pi.absorption()
    assert a["absorbing"] == "sellers" and a["aggressor"] == "buyers"
    assert a["score"] > 40, f"an adverse move must not score zero (got {a['score']})"

# ═══════════════════════════════════════════════════════════════
# MetaTrader 5 bridge probe — every stage reports honestly
# ═══════════════════════════════════════════════════════════════

class _FakeMT5:
    """Stand-in for the MetaTrader5 module: records the call it received."""

    def __init__(self, init_ok=True, last_error=(0, "no error"), account=True, terminal=True):
        self.init_ok = init_ok
        self._last_error = last_error
        self.asked: list[dict] = []
        self.shut = 0
        self._account = account
        self._terminal = terminal
        self.symbols = {"USTEC": True, "XAUUSD": False}

    def initialize(self, **kwargs):
        self.asked.append(kwargs)
        return self.init_ok

    def last_error(self):
        return self._last_error

    def terminal_info(self):
        if not self._terminal:
            return None
        return SimpleNamespace(name="MetaTrader 5", company="Test Broker", path="C:/MT5/terminal64.exe",
                               connected=True, build=4200)

    def account_info(self):
        if not self._account:
            return None
        return SimpleNamespace(login=12345678, server="TestBroker-Demo", currency="USD",
                               leverage=100, name="should never be returned")

    def symbol_info(self, sym):
        return object() if self.symbols.get(sym) else None

    def shutdown(self):
        self.shut += 1


def test_mt5_probe_names_the_missing_stage(monkeypatch):
    """No package → the stage says so and carries the exact install command."""
    from orderflow_system.desktop import engine as eng

    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name == "MetaTrader5":
            raise ImportError("no MetaTrader5")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    out = eng.mt5_probe({})
    assert out["ok"] is False
    assert out["stage"] in ("platform", "package")
    if out["stage"] == "package":
        # the command must fit this environment: uv venvs ship without pip
        assert "MetaTrader5" in out["command"]
        assert ("-m pip install" in out["command"]) or ("uv pip install" in out["command"])


def test_mt5_probe_reports_a_terminal_that_refuses(monkeypatch):
    """Package present, terminal not reachable → name the cause, never claim success."""
    from orderflow_system.desktop import engine as eng

    fake = _FakeMT5(init_ok=False, last_error=(-10003, "IPC timeout"))
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    out = eng.mt5_probe({"path": r"C:\Program Files\MT5\terminal64.exe"})
    assert out["ok"] is False and out["stage"] == "terminal"
    assert "IPC timeout" in out["message"] and out["error_code"] == -10003
    assert fake.shut == 0, "nothing to shut down when initialize failed"


def test_mt5_probe_success_reports_account_and_symbols(monkeypatch):
    """Ready → terminal + account + per-symbol availability, no password echoed."""
    from orderflow_system.desktop import engine as eng

    fake = _FakeMT5()
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    out = eng.mt5_probe({
        "path": r"C:\Program Files\MT5\terminal64.exe",
        "login": 12345678, "password": "hunter2-not-echoed", "server": "TestBroker-Demo",
        "symbols": ["USTEC", "XAUUSD"],
    })
    assert out["ok"] is True and out["stage"] == "ready"
    assert out["terminal"]["company"] == "Test Broker" and out["terminal"]["build"] == 4200
    assert out["account"] == {"login": 12345678, "server": "TestBroker-Demo",
                              "currency": "USD", "leverage": 100}
    assert "name" not in out["account"], "no account holder PII in the response"
    assert json.dumps(out).find("hunter2") == -1, "the password must never come back"
    assert out["symbols"] == {"USTEC": True, "XAUUSD": False}
    assert fake.shut == 1, "the probe must shut the bridge down again"
    assert fake.asked[0]["login"] == 12345678 and fake.asked[0]["server"] == "TestBroker-Demo"


def test_mt5_probe_tolerates_a_terminal_without_account_info(monkeypatch):
    """A terminal with no account signed in is still a usable bridge."""
    from orderflow_system.desktop import engine as eng

    fake = _FakeMT5(account=False, terminal=True)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    out = eng.mt5_probe({})
    assert out["ok"] is True and out["account"] is None
    assert out["terminal"]["connected"] is True and fake.shut == 1


def test_mt5_probe_offers_a_command_that_fits_the_environment():
    """A uv-made venv has no pip: the suggested install line must still be runnable."""
    from orderflow_system.desktop import engine as eng

    import importlib.util
    out = eng.mt5_probe({})
    if out["stage"] == "package":
        has_pip = importlib.util.find_spec("pip") is not None
        cmd = out["command"]
        assert ("-m pip install" in cmd) if has_pip else ("uv pip install" in cmd), cmd


# ═══════════════════════════════════════════════════════════════
# VWAP suite, trade detector, scanner, delta bars (the reference platform pass)
# ═══════════════════════════════════════════════════════════════

def test_vwap_matches_a_hand_calculation_and_bands_use_weighted_sigma():
    """VWAP = Σpv/Σv, σ² = Σp²v/Σv − VWAP² — checked against arithmetic done by hand."""
    from orderflow_system.atlas.vwap import VWAPStudy

    pi = VWAPStudy("T", tick_size=0.1, window_s=3600)
    t = NOW()
    prints = [(100.0, 2.0), (101.0, 1.0), (102.0, 1.0)]      # Σpv = 403, Σv = 4 → 100.75
    for i, (px, sz) in enumerate(prints):
        pi.on_tick(tick(t + i * 1000, px, sz, "buy"))
    snap = pi.snapshot()
    assert snap["vwap"] == pytest.approx(100.75, abs=1e-6)
    pv = 100.0 * 2 + 101.0 * 1 + 102.0 * 1
    p2v = 100.0 ** 2 * 2 + 101.0 ** 2 + 102.0 ** 2
    expected_sigma = ((p2v / 4) - (pv / 4) ** 2) ** 0.5
    assert snap["sigma"] == pytest.approx(expected_sigma, abs=1e-6)   # payload rounds to 8dp
    assert snap["bands"][0]["upper"] == pytest.approx(100.75 + expected_sigma, abs=1e-6)
    assert snap["bands"][2]["lower"] == pytest.approx(100.75 - 3 * expected_sigma, abs=1e-6)
    assert snap["volume"] == pytest.approx(4.0)


def test_vwap_rolling_window_drops_old_prints():
    """The window is real: a print older than the window must leave the average."""
    from orderflow_system.atlas.vwap import VWAPStudy

    pi = VWAPStudy("T", tick_size=0.1, window_s=60, history_s=100)
    now = NOW()
    pi.on_tick(tick(now - 300_000, 50.0, 10.0, "buy"))       # five minutes ago → outside
    pi.on_tick(tick(now - 30_000, 100.0, 1.0, "buy"))
    pi.on_tick(tick(now - 20_000, 102.0, 1.0, "buy"))
    snap = pi.snapshot()
    assert snap["vwap"] == pytest.approx(101.0, abs=1e-6), "the stale print must not weigh in"


def test_vwap_cross_fires_once_per_direction():
    """A cross needs a real side change and respects its cooldown."""
    from orderflow_system.atlas.vwap import VWAPStudy

    pi = VWAPStudy("T", tick_size=0.1, window_s=3600, cross_min_ticks=0.5, cross_cooldown_ms=0)
    t = NOW()
    for i in range(4):
        pi.on_tick(tick(t + i * 1000, 100.0, 5.0, "buy"))
    out_up = pi.on_tick(tick(t + 100_000, 101.0, 5.0, "buy"))     # jumps above → cross
    assert "vwap_cross" in out_up and out_up["vwap_cross"]["side"] == "above"
    assert pi.on_tick(tick(t + 101_000, 101.1, 5.0, "buy")) == {}, "no repeat while above"
    out_down = pi.on_tick(tick(t + 102_000, 99.0, 5.0, "sell"))   # back below → cross
    assert "vwap_cross" in out_down and out_down["vwap_cross"]["side"] == "below"


def test_vwap_anchor_accumulates_only_forward():
    """An anchored VWAP starts at the anchor — nothing in the past is invented."""
    from orderflow_system.atlas.vwap import VWAPStudy

    pi = VWAPStudy("T", tick_size=0.1, window_s=3600)
    t = NOW()
    for i in range(3):
        pi.on_tick(tick(t + i * 1000, 200.0, 1.0, "buy"))
    pi.set_anchor(t + 10_000)
    assert pi.snapshot()["anchored"]["vwap"] == 0.0, "nothing after the anchor yet"
    pi.on_tick(tick(t + 20_000, 300.0, 2.0, "buy"))
    pi.on_tick(tick(t + 21_000, 302.0, 1.0, "sell"))
    anchored = pi.snapshot()["anchored"]
    assert anchored["vwap"] == pytest.approx((300 * 2 + 302 * 1) / 3, abs=1e-6)
    assert anchored["prints"] == 2, "only the prints at or after the anchor count"
    assert anchored["minutes"] >= 0, "an anchor in the future has elapsed nothing yet"


def test_trade_detector_flags_prints_that_eat_depth():
    """A print taking a big share of a large resting order is an execution into depth."""
    from orderflow_system.atlas.tradedepth import TradeDetector

    d = TradeDetector("T", tick_size=0.1, min_share=0.25, size_mult=2.0)
    books = [(100.0, 50.0), (99.9, 5.0), (99.8, 5.0)]
    d.on_orderbook(_book(NOW(), [s for _p, s in books], [1.0, 1.0, 1.0]))
    for _ in range(30):
        d.on_tick(tick(NOW(), 100.0, 0.1, "sell"))            # establish a median print size
    out = d.on_tick(tick(NOW() + 100, 100.0, 30.0, "sell"))    # 30 of 50 resting → 37.5%
    assert "depth_execution" in out, "a 30-lot into 50 resting must register"
    ev = out["depth_execution"][0]
    assert ev["resting"] == 50.0 and ev["share"] == pytest.approx(0.375, abs=0.01)
    small = d.on_tick(tick(NOW() + 200, 100.0, 0.1, "sell"))   # ordinary print
    assert "depth_execution" not in small


def test_trade_detector_marks_a_refill_and_ignores_an_empty_level():
    """Refill = the level comes back after being eaten; a print with no book is not depth."""
    from orderflow_system.atlas.tradedepth import TradeDetector

    d = TradeDetector("T", tick_size=0.1, min_share=0.2, size_mult=2.0, refill_ms=5000)
    d.on_orderbook(_book(NOW(), [40.0, 5.0], [1.0, 1.0]))
    for _ in range(20):
        d.on_tick(tick(NOW(), 100.0, 0.1, "sell"))
    d.on_tick(tick(NOW() + 100, 100.0, 20.0, "sell"))          # eats half the level
    out = d.on_orderbook(_book(NOW() + 1000, [38.0, 5.0], [1.0, 1.0]))   # 95% back
    assert "depth_refill" in out and out["depth_refill"], "the refill must be reported"
    assert d.stats()["refills"] == 1

    empty = TradeDetector("T", tick_size=0.1, min_share=0.2, size_mult=2.0)
    empty.on_orderbook(_book(NOW(), [0.0, 0.0], [0.0, 0.0]))   # nothing resting at the touch
    assert empty.on_tick(tick(NOW() + 5, 100.0, 99.0, "buy")) == {}, "no depth to eat"


def test_delta_bars_close_on_trend_and_reversal():
    """Delta bars are built from effort, not time (the reference platform Price-On-Volume idea)."""
    from orderflow_system.atlas.frames import DeltaBars

    b = DeltaBars("T", tick_size=0.1, trend_delta=10.0, reversal_delta=6.0)
    t = NOW()
    closed = []
    for i in range(3):
        got = b.on_tick(tick(t + i * 100, 100.0 + i * 0.1, 4.0, "buy"))    # +4 each → +12
        if got:
            closed.append(got)
    assert len(closed) == 1, "the trend threshold must close a bar"
    assert closed[0].buy_volume == pytest.approx(12.0)

    b2 = DeltaBars("T", tick_size=0.1, trend_delta=50.0, reversal_delta=5.0)
    for i in range(2):
        b2.on_tick(tick(t + i * 100, 100.0, 4.0, "buy"))                  # +8
    assert b2.on_tick(tick(t + 300, 99.9, 10.0, "sell")) is not None, "a reversal closes the bar"


def test_scanner_ranks_instruments_and_stays_honest_about_its_formula():
    """One row per instrument, sorted, with the score formula stated in the payload."""
    hub = FeatureHub({"extras_enabled": False})
    t = NOW()
    # busy instrument: lots of buys; quiet one: a few sells
    for i in range(400):
        hub.on_tick("BUSYUSDT", tick(t + i * 10, 100.0 + (i % 5) * 0.1, 2.0, "buy"))
    for i in range(20):
        hub.on_tick("QUIETUSDT", tick(t + i * 10, 50.0, 0.5, "sell"))
    table = hub.snapshot_scanner(sort="score", limit=10)
    assert table["count"] == 2 and len(table["rows"]) == 2
    assert table["rows"][0]["symbol"] == "BUSYUSDT", "the busier tape must rank first"
    assert "score = " in table["score_note"], "the heuristic must be stated, not implied"
    busy = table["rows"][0]
    assert busy["volume"] > 0 and busy["prints"] == 400 and busy["delta_pct"] == pytest.approx(100.0)
    # sorting by another column must actually sort
    by_prints = hub.snapshot_scanner(sort="prints", limit=10)
    assert by_prints["rows"][0]["prints"] >= by_prints["rows"][-1]["prints"]


def test_scanner_caches_and_states_that_it_cached():
    hub = FeatureHub({"extras_enabled": False})
    hub.on_tick("AUSDT", tick(NOW(), 10.0, 1.0, "buy"))
    first = hub.snapshot_scanner()
    second = hub.snapshot_scanner()
    assert first["cached"] is False and second["cached"] is True
    assert hub.scanner.stats()["cache_hits"] == 1


def test_trade_detector_ignores_eating_a_small_level():
    """A small resting order being taken is ordinary — only a large one counts."""
    from orderflow_system.atlas.tradedepth import TradeDetector

    d = TradeDetector("T", tick_size=0.1, min_share=0.2, size_mult=2.0, resting_mult=10.0)
    d.on_orderbook(_book(NOW(), [0.5, 5.0], [1.0, 1.0]))       # 0.5 resting at the touch
    for _ in range(30):
        d.on_tick(tick(NOW(), 100.0, 0.1, "sell"))             # median print 0.1
    out = d.on_tick(tick(NOW() + 100, 100.0, 0.4, "sell"))     # eats 80% of a tiny level
    assert "depth_execution" not in out, "a 0.5 level is not a wall — 10× median = 1.0 minimum"
    big = TradeDetector("T", tick_size=0.1, min_share=0.2, size_mult=2.0, resting_mult=10.0)
    big.on_orderbook(_book(NOW(), [40.0, 5.0], [1.0, 1.0]))
    for _ in range(30):
        big.on_tick(tick(NOW(), 100.0, 0.1, "sell"))
    assert "depth_execution" in big.on_tick(tick(NOW() + 100, 100.0, 20.0, "sell"))


# ═══════════════════════════════════════════════════════════════
# the reference platform transfers: tick profile, heatmap carry-forward, bar stats
# ═══════════════════════════════════════════════════════════════

def test_tick_profile_counts_trades_not_volume():
    """A price can be quiet in size and busy in prints — that is what this shows."""
    from orderflow_system.atlas.profiles import MarketProfile

    prof = MarketProfile("T", tick_size=0.1)
    t = NOW()
    # 100.0: three small prints; 100.1: one large print
    for i in range(3):
        prof.on_tick(tick(t + i * 100, 100.0, 0.1, "buy"))
    prof.on_tick(tick(t + 500, 100.1, 5.0, "buy"))
    tp = {r["price"]: r["trades"] for r in prof.snapshot()["tick_profile"]}
    assert tp.get(100.0) == 3 and tp.get(100.1) == 1, tp
    assert prof.poc() == 100.1, "volume POC stays the big print"
    by_trades = max(prof.tick_profile(), key=lambda r: r["trades"])
    assert by_trades["price"] == 100.0, "the tick profile ranks by activity instead"


def test_heatmap_carries_last_known_depth_forward():
    """the reference platform's "extend last known volume": a hole means 'not reported', not 'empty'."""
    from orderflow_system.atlas.depthmap import DepthHeatmap

    hm = DepthHeatmap("T", tick_size=0.1, max_columns=10)
    ts = NOW()

    def book(ts_ms, bid_sizes):
        from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot
        bids = [OrderbookLevel(price=round(100.0 - i * 0.1, 4), quantity=s) for i, s in enumerate(bid_sizes)]
        asks = [OrderbookLevel(price=round(100.1 + i * 0.1, 4), quantity=1.0) for i in range(len(bid_sizes))]
        return OrderbookSnapshot(timestamp_ms=ts_ms, bids=bids, asks=asks)

    hm.on_orderbook(book(ts, [5.0, 5.0, 5.0]))              # column 1 knows all three prices
    hm.on_orderbook(book(ts + 1000, [5.0, 0.0, 0.0]))       # column 2 only knows the touch
    assert hm.carry_forward is False, "off by default: a delta feed deletes levels explicitly"
    hm.carry_forward = True
    snap = hm.snapshot(columns=10, max_rows=20)
    assert snap["carry_forward"] is True
    assert snap["carried_cells"] > 0, "the missing levels must be carried forward"

    hm.carry_forward = False
    fresh = hm.snapshot(columns=10, max_rows=20)
    assert fresh["carried_cells"] == 0, "and the option must actually turn it off"


def test_delta_bars_report_their_statistics():
    """Min/max delta in the bar, and the delta since the extreme was made (Delta SH/SL)."""
    from orderflow_system.atlas.frames import DeltaBars

    b = DeltaBars("T", tick_size=0.1, trend_delta=20.0, reversal_delta=50.0)
    t = NOW()
    b.on_tick(tick(t, 100.0, 6.0, "buy"))         # running delta +6
    b.on_tick(tick(t + 100, 100.2, 4.0, "buy"))   # +10, and a new high
    b.on_tick(tick(t + 200, 100.1, 3.0, "sell"))  # +7
    b.on_tick(tick(t + 300, 99.9, 5.0, "sell"))   # +2, and a new low
    # the closing print must not also be a new extreme, or "delta since the low" is trivially 0
    closed = b.on_tick(tick(t + 400, 100.05, 20.0, "buy"))   # +22 → past the trend threshold
    assert closed is not None, "the trend threshold must close the bar"
    assert closed.delta == pytest.approx(22.0)
    assert closed.delta_max == pytest.approx(22.0), "the closing print is part of the bar, so it is the max"
    assert closed.delta_min == pytest.approx(2.0), "the worst delta reached inside the bar"
    assert closed.delta_sh == pytest.approx(12.0), "delta since the high was made (22 - 10)"
    assert closed.delta_sl == pytest.approx(20.0), "delta since the low was made (22 - 2)"
    assert closed.to_dict()["delta_max"] == pytest.approx(22.0), "the payload carries the same statistics"
