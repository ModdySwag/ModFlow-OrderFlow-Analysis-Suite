"""Price-touch alerts (fold-in plan §3 / A3): the area profile's "watch this level" hand-off.

Pinned here:

1. ``AlertEngine.evaluate_touch`` fires a ``level_touch`` rule on the outside-to-inside
   transition only — price resting at the level fires once, and leaving the band re-arms it.
2. The rule's own scope is the band: ``at_price ± at_tol`` is inclusive at the tolerance edge,
   a rule without a level never fires, a disabled rule is skipped, and cooldown still applies.
3. The hub's tick path carries it: ``FeatureHub.on_tick`` fires the watch, counts it, and the
   alert lands in the same history every detector's firing lands in.
"""

from __future__ import annotations

from orderflow_system.atlas.alerts import AlertEngine
from orderflow_system.atlas.hub import FeatureHub
from orderflow_system.data.models import Side, Tick

RULE = {"id": "ap-t", "name": "watch", "kind": "level_touch", "enabled": True,
        "params": {"at_price": 100.0, "at_tol": 0.5}, "cooldown_s": 0, "channels": ["ui"]}


def engine():
    return AlertEngine([dict(RULE)])


def test_fires_on_the_transition_only_and_rearms():
    eng = engine()
    assert eng.evaluate_touch("X", 99.0, 1000) == []          # outside: quiet
    fired = eng.evaluate_touch("X", 100.2, 2000)              # enters the band
    assert [a.kind for a in fired] == ["level_touch"]
    assert fired[0].data["price"] == 100.0 and fired[0].data["last"] == 100.2
    assert eng.evaluate_touch("X", 100.4, 3000) == []         # still inside: no repeat
    assert eng.evaluate_touch("X", 101.0, 4000) == []         # leaves
    assert len(eng.evaluate_touch("X", 99.8, 5000)) == 1      # returns: fires again
    assert eng.rules[0].fired == 2


def test_tolerance_edge_counts_as_inside():
    assert len(engine().evaluate_touch("X", 100.5, 1000)) == 1      # |100.5 - 100| == at_tol
    assert engine().evaluate_touch("X", 100.51, 1000) == []


def test_a_rule_without_a_level_never_fires_and_disabled_is_skipped():
    eng = AlertEngine([{"id": "no-level", "kind": "level_touch", "params": {}, "cooldown_s": 0}])
    assert eng.evaluate_touch("X", 100.0, 1000) == []
    eng = AlertEngine([dict(RULE, enabled=False)])
    assert eng.evaluate_touch("X", 100.0, 1000) == []


def test_cooldown_still_applies_between_approaches():
    eng = AlertEngine([dict(RULE, cooldown_s=60)])
    assert len(eng.evaluate_touch("X", 100.2, 1_000_000)) == 1      # first approach fires
    assert eng.evaluate_touch("X", 101.0, 1_010_000) == []          # leaves
    assert eng.evaluate_touch("X", 100.2, 1_020_000) == []          # back inside the cooldown: quiet
    assert eng.evaluate_touch("X", 101.0, 1_040_000) == []          # leaves again
    assert len(eng.evaluate_touch("X", 100.2, 1_090_000)) == 1      # 90 s on: fires


def test_removing_the_rule_drops_its_band_state():
    eng = engine()
    eng.evaluate_touch("X", 100.2, 1000)
    eng.remove("ap-t")
    eng.upsert(dict(RULE))
    assert len(eng.evaluate_touch("X", 100.2, 2000)) == 1           # a fresh rule: entry is a transition


def test_history_and_message_read_like_the_rest():
    eng = engine()
    fired = eng.evaluate_touch("BTCUSDT", 100.1, 1000)
    assert fired[0].message == "BTCUSDT: price came back to the watched level 100.0 (±0.5)"
    assert eng.recent(10)[-1]["kind"] == "level_touch"


def test_the_hub_tick_path_carries_the_watch():
    hub = FeatureHub({"alert_rules": [dict(RULE)]})
    hub.on_tick("BTCUSDT", Tick(timestamp_ms=1000, price=100.1, size=0.5, side=Side.BUY))
    assert [a.kind for a in hub.alerts.history] == ["level_touch"]
    assert hub.counters["alerts"] == 1
    # a second tick inside the band is not a second alert
    hub.on_tick("BTCUSDT", Tick(timestamp_ms=2000, price=100.2, size=0.5, side=Side.BUY))
    assert hub.counters["alerts"] == 1
