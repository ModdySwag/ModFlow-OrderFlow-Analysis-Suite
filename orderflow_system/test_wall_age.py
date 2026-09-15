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
    def __init__(self, levels):
        self.bids = [l for l in levels if l.side == "bid"]
        self.asks = [l for l in levels if l.side == "ask"]
        self.timestamp_ms = int(time.time() * 1000)
        self.best_bid = max(l.price for l in self.bids) if self.bids else None
        self.best_ask = min(l.price for l in self.asks) if self.asks else None


def _book(price, size, others=6):
    levels = [Lvl(price - i * 0.5, 1.0) for i in range(1, others)]
    levels.append(Lvl(price, size))
    return Snap(levels)


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
