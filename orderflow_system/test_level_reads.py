"""Level reads (fold-in plan §3): the bar feed dispatches unfinished + node events, and the
atlas levels endpoint serves what the trackers hold.

Pinned here:

1. ``FeatureHub.feed_bar`` turns a closed bar into ``unfinished_business`` / ``node_zone``
   events and runs them through the same ``_dispatch`` → alert-rule path every other
   detection uses — the drawn line and the alert come from one implementation.
2. Rule scope works: a rule listing ``sides: ["below"]`` ignores an above-magnet.
3. ``/api/atlas/levels/{symbol}`` answers with the tracker snapshots plus confluence, and
   says so honestly when the engine has not fed the symbol yet.
"""

from __future__ import annotations

import asyncio

from orderflow_system.atlas.hub import FeatureHub

RULE_UFB = {"id": "ufb", "kind": "unfinished_business", "enabled": True,
            "params": {"min_arms": 1}, "cooldown_s": 0, "channels": ["ui"]}
RULE_NODES = {"id": "nodes", "kind": "node_zone", "enabled": True,
              "params": {"min_count": 2}, "cooldown_s": 0, "channels": ["ui"]}


def test_feed_bar_dispatches_unfinished_and_node_events():
    hub = FeatureHub({"alert_rules": [dict(RULE_UFB), dict(RULE_NODES)]})
    bar = {100.0: (1.0, 0.0), 100.5: (2.0, 1.0)}       # top row bids -> unfinished high at 100.5

    ev1 = hub.feed_bar("BTCUSDT", 60_000, dict(bar), tick_size=0.1)
    assert [e["kind"] for e in ev1] == ["unfinished_business"]
    assert ev1[0]["price"] == 100.5 and ev1[0]["side"] == "above"
    assert [a.kind for a in hub.alerts.history] == ["unfinished_business"]

    # the same bar again: the return fixes the first magnet, a new one forms (arms = 2),
    # and the shared POC makes the node run cross its 2-bar threshold
    ev2 = hub.feed_bar("BTCUSDT", 120_000, dict(bar), tick_size=0.1)
    kinds = [e["kind"] for e in ev2]
    assert "unfinished_fixed" in kinds and "unfinished_business" in kinds and "node_zone" in kinds
    fired = [a.kind for a in hub.alerts.history]
    assert fired.count("unfinished_business") == 2 and "node_zone" in fired


def test_feed_bar_respects_sides_scope():
    rule = dict(RULE_UFB)
    rule["params"] = {"sides": ["below"], "min_arms": 1}
    hub = FeatureHub({"alert_rules": [rule]})

    hub.feed_bar("X", 1000, {100.0: (1.0, 0.0), 100.5: (2.0, 1.0)}, tick_size=0.1)   # above magnet
    assert hub.alerts.history == []

    hub.feed_bar("X", 2000, {99.5: (0.0, 3.0), 100.0: (0.0, 0.0)}, tick_size=0.1)    # below magnet
    assert [a.kind for a in hub.alerts.history] == ["unfinished_business"]


def test_levels_endpoint_serves_tracker_snapshots():
    from orderflow_system.atlas.api import atlas_levels
    from orderflow_system.atlas.hub import hub as atlas_singleton

    atlas_singleton.feed_bar("ZZZLEVELS", 60_000,
                             {100.0: (1.0, 0.0), 100.5: (2.0, 1.0)}, tick_size=0.1)
    payload = asyncio.run(atlas_levels("ZZZLEVELS", 2.0))
    assert payload["ok"] is True
    open_prices = [lv["price"] for lv in payload["unfinished"]["open"]]
    assert 100.5 in open_prices
    assert isinstance(payload["confluence"], list)


def test_levels_endpoint_is_honest_without_a_feed():
    from orderflow_system.atlas.api import atlas_levels

    payload = asyncio.run(atlas_levels("NEVERFED_XYZ", 2.0))
    assert payload["ok"] is True
    assert payload["unfinished"] is None and payload["nodes"] is None
    assert "no live readings" in payload["note"]
