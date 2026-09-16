"""§56: the heat wire round-trips, and the `wall` kind finally has a live detector."""

from __future__ import annotations

from orderflow_system.atlas.depthmap import DepthHeatmap
from orderflow_system.atlas.wire import MAGIC, decode_heat_bin, pack_heatmap_bin
from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot

T0 = 1_700_000_000_000


def _snap():
    return {
        "symbol": "T", "version": 7, "step": 0.5, "tick": 0.5, "upper_cutoff_pct": 1.0,
        "carry_forward": True, "carried_cells": 2, "scale_max": 9.0, "wall_age_ms": 120000,
        "buckets": [T0, T0 + 1000],
        "prices": [100.0, 100.5],                     # the flat price ladder (2 rows)
        "values": [[5.0, 3.0], [2.0, 1.0]],           # values[price row][time column]
        "traded": [[1.0, 0.5], [0.0, 0.0]],
        "best": [{"bid": 100.0, "ask": 100.5, "trades": 4}],
        "events": [{"ts_ms": T0, "price": 100.0, "kind": "wall", "size": 5.0}],
        "walls": [{"price": 100.0, "size": 5.0, "held_ms": 0}],
    }


def test_wire_round_trips_the_snapshot():
    packed = pack_heatmap_bin(_snap())
    assert packed[:4] == MAGIC
    out = decode_heat_bin(packed)
    h = out["header"]
    assert (h["symbol"], h["cols"], h["rows"], h["version"]) == ("T", 2, 2, 7)
    assert h["events"][0]["kind"] == "wall" and h["walls"][0]["price"] == 100.0
    assert out["buckets"] == [float(T0), float(T0 + 1000)]
    assert out["prices"] == [100.0, 100.5]                         # flat ladder, row-major sections
    assert out["values"] == [5.0, 3.0, 2.0, 1.0]
    assert out["traded"] == [1.0, 0.5, 0.0, 0.0]
    # one best record per COLUMN — the fixture carries one, the second column reads zeros
    assert out["best"] == [{"bid": 100.0, "ask": 100.5, "trades": 4},
                           {"bid": 0.0, "ask": 0.0, "trades": 0}]
    assert out["consumed"] == len(packed)                      # nothing left on the floor


def test_wire_flat_prices_and_empty_payloads():
    snap = _snap()
    snap["prices"] = [100.0, 100.5]                            # already flat — the ladder IS the price axis
    out = decode_heat_bin(pack_heatmap_bin(snap))
    assert out["header"]["prices_mode"] == "flat"
    assert out["prices"] == [100.0, 100.5]
    assert out["values"] == [5.0, 3.0, 2.0, 1.0]               # the row-major walk is the same either way

    per_col = _snap()
    per_col["prices"] = [[100.0, 100.5], [100.0, 100.5]]       # a legacy per-column producer
    out3 = decode_heat_bin(pack_heatmap_bin(per_col))
    assert out3["header"]["prices_mode"] == "per_column"
    assert out3["prices"] == [100.0, 100.5, 100.0, 100.5]
    assert out3["values"] == [5.0, 3.0, 2.0, 1.0]

    empty = pack_heatmap_bin({"symbol": "T", "buckets": [], "prices": [], "values": []})
    out2 = decode_heat_bin(empty)
    assert out2["header"]["cols"] == 0 and out2["values"] == [] and out2["best"] == []


def test_bin_route_exists():
    from orderflow_system.atlas.api import router

    paths = {getattr(r, "path", "") for r in router.routes}
    assert any(p.endswith("/heatmap/{symbol}/bin") for p in paths), sorted(paths)[:20]


def _book(ts, bids, asks):
    return OrderbookSnapshot(timestamp_ms=ts,
                             bids=[OrderbookLevel(price=p, quantity=q) for p, q in bids],
                             asks=[OrderbookLevel(price=p, quantity=q) for p, q in asks])


def test_wall_events_fire_on_entry_only():
    hm = DepthHeatmap("T", tick_size=0.5, bucket_ms=1000, wall_quantile=0.5)
    # first snapshot: the top levels register and fire once (a wall that exists at boot is a fact)
    hm.on_orderbook(_book(T0, [(100.0, 10.0), (99.5, 2.0)], [(100.5, 2.0)]))
    first = [e for e in hm.snapshot()["events"] if e["kind"] == "wall"]
    assert first and all("of visible resting size" in e["detail"] for e in first)

    # same book again: a standing wall must NOT re-fire
    hm.on_orderbook(_book(T0 + 1000, [(100.0, 10.0), (99.5, 2.0)], [(100.5, 2.0)]))
    again = [e for e in hm.snapshot()["events"] if e["kind"] == "wall"]
    assert len(again) == len(first), "wall re-fired without leaving the band"

    # a fresh level crossing the band fires exactly one new event
    hm.on_orderbook(_book(T0 + 2000, [(100.0, 10.0), (99.5, 2.0), (99.0, 40.0)], [(100.5, 2.0)]))
    third = [e for e in hm.snapshot()["events"] if e["kind"] == "wall"]
    assert len(third) == len(first) + 1
    newest = third[-1]
    assert newest["price"] == 99.0 and newest["size"] == 40.0
