"""Wall age is a duration, not a freshness: the streak must start when a level begins holding and
break when it stops; and an alert rule bound to a price must only fire at that price."""
from __future__ import annotations

import time

from orderflow_system.atlas.alerts import AlertEngine
from orderflow_system.atlas.depthmap import DepthHeatmap


class Lvl:
    def __init__(self, price, quantity, side="bid"):
        self.price = price
        self.quantity = quantity
        self.side = side


class Snap:
    def __init__(self, levels, ts_ms=None):
        self.bids = [l for l in levels if l.side == "bid"]
        self.asks = [l for l in levels if l.side == "ask"]
        self.timestamp_ms = int(ts_ms if ts_ms is not None else time.time() * 1000)
        self.best_bid = max(l.price for l in self.bids) if self.bids else None
        self.best_ask = min(l.price for l in self.asks) if self.asks else None


def _book(price, size, others=6, ts_ms=None):
    levels = [Lvl(price - i * 0.5, 1.0) for i in range(1, others)]
    levels.append(Lvl(price, size))
    return Snap(levels, ts_ms=ts_ms)


def test_wall_age_needs_a_held_streak():
    hm = DepthHeatmap("T", tick_size=0.5, wall_age_ms=1_000)
    t0 = int(time.time() * 1000)
    hm.on_orderbook(_book(100.0, 500.0), ts_ms=t0)
    assert hm.events("wall_age") == []                     # just appeared: no duration yet
    hm.on_orderbook(_book(100.0, 500.0), ts_ms=t0 + 1_500)
    fired = hm.events("wall_age")
    assert fired, "a wall that held past the threshold must be reported"
    assert "held" in str(fired[-1]), "the event records how long the level held"

    # the streak breaks when the level stops qualifying, and a later wall starts a fresh clock
    hm.on_orderbook(_book(100.0, 0.1), ts_ms=t0 + 2_000)
    assert hm.wall_durations() == []
    hm.on_orderbook(_book(100.0, 500.0), ts_ms=t0 + 2_500)
    hm.on_orderbook(_book(100.0, 500.0), ts_ms=t0 + 3_000)
    assert len(hm.events("wall_age")) == 1, "the fresh streak is not old enough yet"


def test_rule_bound_to_a_price_fires_only_there():
    eng = AlertEngine()
    eng.set_rules([{
        "id": "hm-test", "name": "level", "kind": "heat_pull", "enabled": True,
        "params": {"min_size": 1.0, "at_price": 100.0, "at_tol": 0.5},
        "cooldown_s": 0, "channels": ["ui"],
    }])
    assert eng.evaluate("T", "heat_pull", {"price": 100.0, "size": 5.0}), "the bound level must fire"
    assert eng.evaluate("T", "heat_pull", {"price": 103.0, "size": 5.0}) == [], "another level must not"
    assert eng.evaluate("T", "heat_pull", {"price": 100.4, "size": 5.0}), "inside the tolerance it fires"
    assert eng.evaluate("T", "heat_pull", {"size": 5.0}) == [], "no price means no evidence"


def test_the_maps_own_events_reach_the_alert_engine():
    """A held level fires a rule bound to it — through the hub, the way the app runs.

    The depth map has recorded wall_age / pull / stack events since P1-6 and the hub has mapped
    "pull"/"stack" to their alert kinds since the atlas package landed, but nothing ever called
    `_dispatch` with them: every rule the heatmap's alert buttons create (and the two default heat
    rules) could not fire at all. This walks the real path — snapshot in, alert out.
    """
    from orderflow_system.atlas.hub import FeatureHub

    hub = FeatureHub({"alert_rules": [{
        "id": "hm-T-100_0-000001", "name": "T 100 · holds", "kind": "wall_age", "enabled": True,
        "params": {"min_size": 1.0, "at_price": 100.0, "at_tol": 0.5, "min_age_s": 1},
        "cooldown_s": 0, "channels": ["ui"],
    }]})
    heatmap = hub.ensure("T", 0.5).heatmap
    heatmap.wall_age_ms = 1_000                      # the map's own threshold, for a 1 s test
    t0 = int(time.time() * 1000)
    two_walls = [Lvl(100.0, 500.0), Lvl(101.0, 500.0)] + [Lvl(99.0 - i * 0.5, 1.0) for i in range(1, 6)]

    hub.on_orderbook("T", Snap(two_walls, ts_ms=t0))
    assert hub.alerts.recent(limit=5) == [], "a level that just appeared has no duration yet"
    hub.on_orderbook("T", Snap(two_walls, ts_ms=t0 + 1_500))

    assert len(heatmap.events("wall_age")) == 2, "both held levels are events"
    fired = [a for a in hub.alerts.recent(limit=5) if a["kind"] == "wall_age"]
    assert len(fired) == 1, "two held levels, one rule bound to 100 — only that one may fire"
    alert = fired[-1]
    assert alert["symbol"] == "T" and alert["data"]["price"] == 100.0
    assert alert["data"]["held_ms"] == 1_500, "the event says how long the level held"
    assert "held" in alert["message"] and "100" in alert["message"], alert["message"]


def test_a_pull_at_a_bound_level_reaches_the_engine():
    """The kind the heatmap's "alert on cursor level" creates — a pull near the level, not a hold."""
    from orderflow_system.atlas.hub import FeatureHub
    from orderflow_system.data.models import Side, Tick

    hub = FeatureHub({"alert_rules": [{
        "id": "hm-T-100_0-000002", "name": "T 100 · pulled", "kind": "heat_pull", "enabled": True,
        "params": {"min_size": 10.0, "at_price": 100.0, "at_tol": 0.5},
        "cooldown_s": 0, "channels": ["ui"],
    }]})
    hub.on_tick("T", Tick(timestamp_ms=int(time.time() * 1000), price=100.0, size=0.5, side=Side.BUY))
    hub.on_orderbook("T", _book(100.0, 500.0))                       # a wall is resting at 100
    hub.on_orderbook("T", _book(100.0, 50.0))                        # 450 of it pulled, near price

    fired = [a for a in hub.alerts.recent(limit=5) if a["kind"] == "heat_pull"]
    assert fired, "a pull near the bound level must reach the engine"
    assert "pulled" in fired[-1]["message"], fired[-1]["message"]
    assert fired[-1]["data"]["price"] == 100.0


def test_a_hold_scope_needs_the_evidence_and_bounds_the_rule():
    """`min_age_s` is the field the heatmap's hold-alert fills in, and the engine honours it."""
    eng = AlertEngine([{
        "id": "hm-hold", "name": "holds", "kind": "wall_age", "enabled": True,
        "params": {"at_price": 100.0, "at_tol": 0.5, "min_age_s": 120},
        "cooldown_s": 0, "channels": ["ui"],
    }])
    assert eng.evaluate("T", "wall_age", {"price": 100.0, "size": 5.0}) == [], "no held_ms, no evidence"
    assert eng.evaluate("T", "wall_age", {"price": 100.0, "size": 5.0, "held_ms": 60_000}) == [], \
        "60 s is short of the 120 s the rule asks for"
    assert eng.evaluate("T", "wall_age", {"price": 100.0, "size": 5.0, "held_ms": 130_000})
    assert eng.evaluate("T", "wall_age", {"price": 103.0, "size": 5.0, "held_ms": 300_000}) == [], \
        "the level scope still applies"


def test_the_hold_alert_size_floor_is_the_one_the_form_offers():
    """The editor offers min_size on wall_age; it has to be a threshold, not decoration."""
    eng = AlertEngine([{
        "id": "hm-size", "name": "holds big", "kind": "wall_age", "enabled": True,
        "params": {"min_size": 2.0, "at_price": 100.0, "at_tol": 0.5},
        "cooldown_s": 0, "channels": ["ui"],
    }])
    assert eng.evaluate("T", "wall_age", {"price": 100.0, "size": 1.0, "held_ms": 200_000}) == []
    assert eng.evaluate("T", "wall_age", {"price": 100.0, "size": 3.0, "held_ms": 200_000})
