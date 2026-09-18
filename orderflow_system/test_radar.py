"""Level Radar (G1, fold-in plan §4) — the lifecycle machine, pinned.

Pure half (`test_rt_*`): the transition matrix on price series — approach, defense (first test),
confluence confirmation, spent vs failed, silent re-arm, expiry, spent retention, merge, summary.
Wiring half (`test_wire_*`): the hub registers levels from closed bars and from the area-profile
rules, tick transitions dispatch as `radar_level` detections (so an alert rule fires through the
same pipe every detection rides), the level hook sees only NEW levels (U3's seam), the scanner
carries the Radar columns, and the endpoints are honest before the engine has fed a symbol.
"""

from __future__ import annotations

import asyncio

from orderflow_system.atlas.hub import FeatureHub
from orderflow_system.atlas.radar import RadarTracker
from orderflow_system.data.models import Side, Tick


def mk(tick=0.1, **kw):
    return RadarTracker(symbol="X", tick_size=tick, **kw)


def ev_states(events):
    return [e["state"] for e in events]


# ── pure half ────────────────────────────────────────────────────

def test_rt_registration_arms_and_records_side():
    t = mk()
    lv, is_new = t.register(100.0, "node", 1000, strength=60.0, ref_price=101.0)
    assert is_new and lv.state == "armed" and lv.side == "above"
    assert lv.tol == 0.2 and lv.sources == ["node"] and lv.id == "X:node:1"
    lv2, is_new2 = t.register(100.05, "unfinished", 1100, strength=70.0, ref_price=101.0)
    assert lv2 is lv and not is_new2 and lv.sources == ["node", "unfinished"]
    assert lv.strength == 70.0


def test_rt_approach_and_silent_rearm():
    t = mk()
    t.register(100.0, "node", 0)
    assert ev_states(t.step(100.4, 1)) == ["approaching"]      # band = 2.5 x 0.2 = 0.5
    assert ev_states(t.step(100.6, 2)) == []                   # out of band: silent armed again
    assert t.levels[0].state == "armed"
    assert ev_states(t.step(100.4, 3)) == ["approaching"]


def test_rt_defense_counts_the_first_test():
    t = mk()
    t.register(100.0, "poc", 0, ref_price=101.0)
    assert ev_states(t.step(100.4, 1)) == ["approaching"]
    assert ev_states(t.step(100.1, 2)) == []                   # inside ±tol: a test starts
    assert t.levels[0].test_side == "above"
    out = t.step(100.4, 3)                                     # left on the entry side: held
    assert ev_states(out) == ["defended"]
    lv = t.levels[0]
    assert lv.touches == 1 and lv.defenses == 1 and out[0]["first_test"] is True
    t.step(100.1, 4)
    out2 = t.step(100.4, 5)
    assert ev_states(out2) == ["defended"] and out2[0]["first_test"] is False
    assert lv.touches == 2


def test_rt_two_sources_defend_to_confirmed():
    t = mk()
    t.register(100.0, "node", 0, ref_price=101.0)
    t.register(100.05, "virgin_poc", 1, ref_price=101.0)       # merges: sources 2
    t.step(100.1, 2)
    out = t.step(100.4, 3)
    assert ev_states(out) == ["confirmed"]
    assert out[0]["sources"] == ["node", "virgin_poc"]


def test_rt_pass_through_spends_and_later_break_fails():
    t = mk()
    t.register(100.0, "node", 0, ref_price=101.0)
    t.step(100.1, 1)                                           # test starts (from above)
    out = t.step(99.7, 2)                                      # exits the far side, never held
    assert ev_states(out) == ["spent"] and t.levels[0].state == "spent"

    t2 = mk()
    t2.register(100.0, "node", 0, ref_price=101.0)
    t2.step(100.1, 1)
    assert ev_states(t2.step(100.4, 2)) == ["defended"]        # held once
    t2.step(100.1, 3)
    out2 = t2.step(99.7, 4)                                    # returns and breaks: failed
    assert ev_states(out2) == ["failed"] and t2.levels[0].state == "failed"


def test_rt_big_jump_crossing_spends_without_a_test():
    t = mk()
    t.register(100.0, "node", 0, ref_price=101.0)
    out = t.step(99.5, 1)                                      # straight to the far side
    assert ev_states(out) == ["spent"] and t.levels[0].test_side == ""


def test_rt_expiry_and_spent_retention():
    t = mk(max_age_ms=60_000, spent_keep_ms=10_000)
    t.register(100.0, "node", 0)
    t.step(105.0, 61_000)                                      # never approached; past max age
    assert t.levels == []

    t2 = mk(max_age_ms=600_000, spent_keep_ms=10_000)
    t2.register(100.0, "node", 0, ref_price=101.0)
    t2.step(99.5, 1)                                           # spent at ts 1
    t2.step(105.0, 5_000)
    assert len(t2.levels) == 1                                 # still visible inside the keep window
    t2.step(105.0, 20_000)
    assert t2.levels == []                                     # dropped after it


def test_rt_summary_counts_and_score():
    t = mk()
    t.register(100.0, "node", 0, ref_price=101.0)
    t.register(110.0, "poc", 0, ref_price=109.0)
    t.step(100.4, 1)                                           # one approaching
    s = t.summary()
    assert s["armed"] == 1 and s["approaching"] == 1 and s["live"] == 2
    assert s["note"] == "1 armed · 1 approaching · 0 held"
    assert s["score"] == round(100.0 * min(1.0, 1 / 6.0), 1)


# ── wiring half ──────────────────────────────────────────────────

RULE_RADAR = {"id": "radar-t", "kind": "radar_level", "enabled": True,
              "params": {"states": ["defended"]}, "cooldown_s": 0, "channels": ["ui"]}


def test_wire_feed_bar_registers_magnets_and_nodes_and_merges():
    hub = FeatureHub({"alert_rules": [dict(RULE_RADAR)]})
    bar = {100.0: (1.0, 0.0), 100.5: (2.0, 1.0)}
    hub.feed_bar("RADX", 60_000, dict(bar), tick_size=0.1)
    hub.feed_bar("RADX", 120_000, dict(bar), tick_size=0.1)
    feats = hub.symbols["RADX"]
    srcs = sorted({s for lv in feats.radar.levels for s in lv.sources})
    assert "unfinished" in srcs and "node" in srcs
    hit = [lv for lv in feats.radar.levels if abs(lv.price - 100.5) < 0.01]
    assert hit and len(hit[0].sources) == 2                    # the confluence merge


def test_wire_ticks_dispatch_transitions_and_fire_the_alert():
    hub = FeatureHub({"alert_rules": [dict(RULE_RADAR)]})
    # the bar lands first, so the instrument's tick_size (0.1) is the one the radar is built
    # with — a level registered before any tick carries side 'at' and defends the same way.
    hub.feed_bar("RADY", 2000, {100.0: (1.0, 0.0)}, tick_size=0.1)   # magnet at 100.0
    hub.on_tick("RADY", Tick(timestamp_ms=2000, price=100.4, size=0.1, side=Side.BUY))   # approaching
    hub.on_tick("RADY", Tick(timestamp_ms=3000, price=100.1, size=0.1, side=Side.BUY))   # test starts
    hub.on_tick("RADY", Tick(timestamp_ms=4000, price=100.2, size=0.1, side=Side.BUY))   # inside
    hub.on_tick("RADY", Tick(timestamp_ms=5000, price=100.5, size=0.1, side=Side.BUY))   # held
    alerts = [a for a in hub.alerts.history if a.kind == "radar_level"]
    assert len(alerts) == 1
    assert "held" in alerts[0].message and "100.0" in alerts[0].message
    states_seen = sorted({a.data.get("state") for a in alerts})
    assert states_seen == ["defended"]                         # the rule's states scope held


def test_wire_level_hook_sees_new_levels_only():
    seen: list = []
    hub = FeatureHub({"alert_rules": []})
    hub.level_hook = lambda symbol, lvl, price: seen.append((symbol, lvl.source, round(lvl.price, 2)))
    bar = {100.0: (1.0, 0.0), 100.5: (2.0, 1.0)}
    hub.feed_bar("RADH", 60_000, dict(bar), tick_size=0.1)
    n1 = len(seen)
    assert n1 >= 1 and all(s[0] == "RADH" for s in seen)
    hub.feed_bar("RADH", 120_000, dict(bar), tick_size=0.1)    # merges: no new levels
    assert len(seen) == n1


def test_wire_scanner_carries_the_radar_fields():
    hub = FeatureHub({"alert_rules": []})
    hub.on_tick("RADZ", Tick(timestamp_ms=1000, price=101.0, size=1.0, side=Side.BUY))
    hub.feed_bar("RADZ", 2000, {100.0: (1.0, 0.0), 100.5: (2.0, 1.0)}, tick_size=0.1)
    out = hub.snapshot_scanner(sort="radar_score", limit=10)
    rows = [r for r in out["rows"] if r["symbol"] == "RADZ"]
    assert rows
    row = rows[0]
    assert "radar_score" in row and "radar_approaching" in row and "radar_note" in row
    assert isinstance(row["radar_note"], str) and "armed" in row["radar_note"]


def test_wire_radar_endpoints_are_honest_without_a_feed():
    from orderflow_system.atlas.api import radar_all, radar_symbol

    payload = asyncio.run(radar_symbol("NEVERFED_RADAR"))
    assert payload["ok"] is True and payload["counts"] is None
    assert "no live readings" in payload["note"]
    assert asyncio.run(radar_all())["ok"] is True
