"""
W9 — synthetic instruments and spreads: the definitions, the composition and the divergence read.

The claim this file is about: a synthetic instrument is honest arithmetic over series this build
already stores. Concretely, all of it offline and on fixtures:

* a definition is validated by name (unknown kind, no legs, a zero weight, one side only, the same
  instrument twice) and a submitted one comes back canonicalised with a stable id;
* the settings block coerces and clamps, and unreadable definitions can never empty the panel;
* legs are unioned onto one grid and forward-filled — never backwards past a leg's first print, and
  never across a gap wider than `max_gap_ms` — with how much was carried reported per leg;
* the four kinds compose the arithmetic they claim: a ratio is a ratio, a basket is a weighted
  average, a basis is a fraction of the leg it is measured against (bps), a spread is a difference;
* the divergence statistics are computable by hand on the fixtures (z, the share beyond sigma, the
  legs' correlation), and a composite that has not moved reports no z instead of a zero;
* the refusal path names the leg it could not read ("no stored history for X — open its chart
  first") and the route answers it that way instead of inventing a series.

Run:  .venv/Scripts/python.exe -m pytest orderflow_system/test_synthetic.py -q
"""

from __future__ import annotations

import asyncio
import math
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from orderflow_system.atlas import synthetic

MINUTE = 60_000
#: A fixed epoch ms ON a minute boundary (so every fixture buckets exactly once): the whole
#: file is deterministic, and no test depends on when it runs.
T0 = 1_700_000_000_000 - (1_700_000_000_000 % MINUTE)


def series(prices: list[float], *, start: int = T0, step: int = MINUTE) -> list[dict[str, Any]]:
    """The leg shape the route hands to compose(): plain {ts_ms, price} rows, oldest first."""
    return [{"ts_ms": start + index * step, "price": float(price)}
            for index, price in enumerate(prices)]


def ratio_def(**over: Any) -> dict[str, Any]:
    base = {"name": "ETH/BTC ratio", "kind": "ratio",
            "legs": [{"symbol": "ETHUSDT", "side": 1}, {"symbol": "BTCUSDT", "side": -1}]}
    base.update(over)
    return base


def basket_def(**over: Any) -> dict[str, Any]:
    base = {"name": "Majors basket", "kind": "basket",
            "legs": [{"symbol": "BTCUSDT", "side": 1, "weight": 0.5},
                     {"symbol": "ETHUSDT", "side": 1, "weight": 0.5}]}
    base.update(over)
    return base


# ── the settings block ─────────────────────────────────────────────────────────────────────────

def test_clean_returns_the_starters_for_anything_unreadable():
    for patch in (None, [], "nope", 7, {"definitions": "nope"}):
        out = synthetic.clean(patch)
        assert [d["id"] for d in out["definitions"]] == list(synthetic.STARTER_IDS)
        assert out["window_min"] == synthetic.DEFAULTS["window_min"]
        assert out["z_stretch"] == synthetic.DEFAULTS["z_stretch"]


def test_clean_clamps_every_bound_and_defaults_every_type():
    out = synthetic.clean({"window_min": 1, "align_ms": 5, "max_gap_ms": -4, "min_samples": 9_000,
                           "z_stretch": "abc", "max_points": 10 ** 6, "refresh_ms": "soon",
                           "unknown_key": 1})
    assert out["window_min"] == 10                       # the lowest window the panel prints
    assert out["align_ms"] == 15_000
    assert out["max_gap_ms"] == 0
    assert out["min_samples"] == 500
    assert out["z_stretch"] == synthetic.DEFAULTS["z_stretch"]   # a non-number is not a stretch
    assert out["max_points"] == 2_000
    assert out["refresh_ms"] == synthetic.DEFAULTS["refresh_ms"]
    assert "unknown_key" not in out
    high = synthetic.clean({"window_min": 99_999, "align_ms": 10 ** 9, "z_stretch": 99})
    assert (high["window_min"], high["align_ms"], high["z_stretch"]) == (10_080, 3_600_000, 4.0)


def test_clean_keeps_the_readable_definitions_and_drops_the_rest():
    out = synthetic.clean({"definitions": [
        {"name": "Good spread", "kind": "spread",
         "legs": [{"symbol": "A", "side": "long"}, {"symbol": "B", "side": "short", "weight": 2}]},
        {"name": "", "kind": "ratio", "legs": [{"symbol": "A", "side": 1}]},   # no name
        {"name": "Wrong", "kind": "wat", "legs": [{"symbol": "A", "side": 1}]},  # unknown kind
        {"name": "One sided", "kind": "ratio", "legs": [{"symbol": "A", "side": 1}]},
        {"name": "Zero weight", "kind": "basket",
         "legs": [{"symbol": "A", "side": 1, "weight": 0}]},
    ]})
    assert [d["id"] for d in out["definitions"]] == ["good-spread"]
    assert out["definitions"][0]["legs"] == [{"symbol": "A", "side": 1, "weight": 1.0},
                                             {"symbol": "B", "side": -1, "weight": 2.0}]


def test_the_starter_definitions_pass_their_own_validator():
    for starter in synthetic.STARTERS:
        definition, problems = synthetic.check_definition(starter)
        assert problems == [], (starter["id"], problems)
        assert definition is not None
        assert definition["id"] == starter["id"]
    kinds = {d["kind"] for d in synthetic.STARTERS}
    assert {"ratio", "basket", "basis"} <= kinds
    assert len(synthetic.clean(None)["definitions"]) == len(synthetic.STARTERS)


def test_a_definition_keeps_its_stable_id_across_cleans():
    once = synthetic.clean_definition({"name": "BTC Perp  Basis", "kind": "basis",
                                       "legs": [{"symbol": "a", "side": 1},
                                                {"symbol": "b", "side": -1}]})
    assert once["id"] == "btc-perp-basis"
    again = synthetic.clean_definition(dict(once, name=once["name"]))
    assert again["id"] == once["id"]
    renamed = synthetic.clean_definition(dict(once, name="Something else"))
    assert renamed["id"] == "btc-perp-basis"         # an explicit id wins over a new name
    assert synthetic.slug("  ") == "synthetic"
    assert synthetic.definition_by_id({"definitions": [once]}, "BTC Perp Basis")["id"] == "btc-perp-basis"


# ── validation ─────────────────────────────────────────────────────────────────────────────────

def test_check_definition_names_every_problem_in_plain_words():
    definition, problems = synthetic.check_definition(
        {"name": "", "kind": "wat", "legs": []})
    assert definition is None
    assert any("give it a name" in problem for problem in problems)
    assert any("kind must be one of" in problem for problem in problems)
    assert any("at least one leg" in problem for problem in problems)

    _, one_weight = synthetic.check_definition(
        {"name": "X", "kind": "spread", "legs": [{"symbol": "A", "side": 1, "weight": 0},
                                                 {"symbol": "B", "side": -1}]})
    assert one_weight and "weight is 0" in one_weight[0]

    _, one_sided = synthetic.check_definition(
        {"name": "X", "kind": "ratio", "legs": [{"symbol": "A", "side": 1}]})
    assert "leg on each side" in one_sided[0]

    _, twice = synthetic.check_definition(
        {"name": "X", "kind": "spread", "legs": [{"symbol": "A", "side": 1},
                                                 {"symbol": "a", "side": -1}]})
    assert "listed twice" in twice[0]

    _, nameless = synthetic.check_definition(
        {"name": "X", "kind": "spread", "legs": [{"weight": 1}, {"symbol": "B", "side": -1}]})
    assert "names no instrument" in nameless[0]

    assert synthetic.check_definition("not an object")[1] == [
        "a synthetic instrument is an object with a name, a kind and at least one leg"]


def test_check_definition_canonicalises_what_it_accepts():
    definition, problems = synthetic.check_definition({
        "name": "  SOL / BTC  ", "kind": "RATIO",
        "legs": [{"symbol": " solusdt ", "side": "long", "weight": "2"},
                 {"symbol": "btcusdt", "side": -1}],
        "note": "  relative value  ",
    })
    assert problems == []
    assert definition == {"id": "sol-btc", "name": "SOL / BTC", "kind": "ratio",
                          "legs": [{"symbol": "SOLUSDT", "side": 1, "weight": 2.0},
                                   {"symbol": "BTCUSDT", "side": -1, "weight": 1.0}],
                          "note": "relative value"}


# ── alignment ──────────────────────────────────────────────────────────────────────────────────

def test_align_unions_the_legs_and_carries_the_last_price_forward():
    grid = synthetic.align({
        "A": [{"ts_ms": T0, "price": 10}, {"ts_ms": T0 + 2 * MINUTE, "price": 30}],
        "B": [{"ts_ms": T0 + MINUTE, "price": 1}, {"ts_ms": T0 + 2 * MINUTE, "price": 2}],
    }, align_ms=MINUTE)
    # T0 belongs to A alone and B has nothing to carry there yet, so it is dropped: the composite
    # starts where both legs can answer.
    assert grid["times"] == [T0 + MINUTE, T0 + 2 * MINUTE]
    assert grid["prices"]["A"] == [10.0, 30.0]
    assert grid["prices"]["B"] == [1.0, 2.0]
    assert grid["carried"] == {"A": 1, "B": 0}


def test_align_never_backfills_past_a_legs_first_print():
    grid = synthetic.align({
        "A": [{"ts_ms": T0, "price": 10}, {"ts_ms": T0 + 3 * MINUTE, "price": 13}],
        "B": [{"ts_ms": T0 + 2 * MINUTE, "price": 1}, {"ts_ms": T0 + 3 * MINUTE, "price": 2}],
    }, align_ms=MINUTE)
    # B has nothing to carry at T0 and T0+1, so those buckets are dropped, not filled.
    assert grid["times"] == [T0 + 2 * MINUTE, T0 + 3 * MINUTE]
    assert grid["prices"]["A"] == [10.0, 13.0]
    assert grid["prices"]["B"] == [1.0, 2.0]


def test_align_refuses_to_carry_across_a_gap_wider_than_max_gap():
    rows_a = [{"ts_ms": T0, "price": 10}, {"ts_ms": T0 + 3 * MINUTE, "price": 13}]
    rows_b = [{"ts_ms": T0 + offset * MINUTE, "price": 1 + offset} for offset in range(4)]
    loose = synthetic.align({"A": rows_a, "B": rows_b}, align_ms=MINUTE, max_gap_ms=2 * MINUTE)
    assert loose["times"] == [T0, T0 + MINUTE, T0 + 2 * MINUTE, T0 + 3 * MINUTE]
    assert loose["prices"]["A"] == [10.0, 10.0, 10.0, 13.0]
    assert loose["carried"]["A"] == 2
    # A gap of exactly max_gap_ms is still carried; one minute more is not.
    tight = synthetic.align({"A": rows_a, "B": rows_b}, align_ms=MINUTE, max_gap_ms=MINUTE)
    assert tight["times"] == [T0, T0 + MINUTE, T0 + 3 * MINUTE]
    assert tight["prices"]["A"] == [10.0, 10.0, 13.0]
    assert tight["carried"]["A"] == 1


def test_align_buckets_to_the_grid_and_the_last_print_in_a_bucket_wins():
    grid = synthetic.align({"A": [{"ts_ms": T0 + 1_000, "price": 10},
                                  {"ts_ms": T0 + 40_000, "price": 11},
                                  {"ts_ms": T0 + 61_000, "price": 12}]}, align_ms=MINUTE)
    assert grid["times"] == [T0, T0 + MINUTE]
    assert grid["prices"]["A"] == [11.0, 12.0]


def test_parse_series_drops_rows_that_carry_no_usable_price():
    rows = [{"ts_ms": T0, "price": 10}, {"ts_ms": T0 + MINUTE, "price": 0},
            {"ts_ms": T0 + 2 * MINUTE}, {"ts_ms": "x", "price": 3}, {"t": T0 + 3 * MINUTE, "close": 4}]
    assert synthetic.parse_series(rows) == [(T0, 10.0), (T0 + 3 * MINUTE, 4.0)]


# ── the four kinds, by hand ────────────────────────────────────────────────────────────────────

def test_a_ratio_is_the_two_legs_prices_divided():
    out = synthetic.compose(ratio_def(), {"ETHUSDT": series([3_000, 3_100, 3_200]),
                                          "BTCUSDT": series([60_000, 62_000, 64_000])})
    assert out["ok"] is True
    assert out["stats"]["value"] == pytest.approx(3_200 / 64_000, abs=1e-8)
    assert out["stats"]["value_unit"] == "ratio"
    assert out["stats"]["spread_abs"] is None            # a ratio has no quote currency
    # The window median of the ratio is the reference for a ratio's bps figure.
    middle = sorted([3_000 / 60_000, 3_100 / 62_000, 3_200 / 64_000])[1]
    assert out["stats"]["spread_bps"] == pytest.approx((3_200 / 64_000 - middle) / middle * 10_000)
    assert out["stats"]["reference_kind"] == "window_median"


def test_a_basket_is_a_weighted_average_and_a_one_sided_composite_is_allowed():
    out = synthetic.compose(basket_def(), {"BTCUSDT": series([60_000, 61_000, 62_000]),
                                           "ETHUSDT": series([3_000, 3_300, 3_600])})
    assert out["ok"] is True
    assert out["stats"]["value"] == pytest.approx(0.5 * 62_000 + 0.5 * 3_600)
    assert out["stats"]["value_unit"] == "price"
    assert out["stats"]["reference_kind"] == "window_median"


def test_a_basis_is_a_fraction_of_the_leg_it_is_measured_against():
    perp = series([60_000, 60_100, 60_200])
    spot = series([59_985, 60_085, 60_185])              # a constant 15-point premium
    out = synthetic.compose({"name": "BTC basis", "kind": "basis",
                             "legs": [{"symbol": "BTCUSDT", "side": 1},
                                      {"symbol": "BTCUSD", "side": -1}]},
                            {"BTCUSDT": perp, "BTCUSD": spot})
    stats = out["stats"]
    assert stats["reference_kind"] == "short_leg"
    assert stats["reference"] == 60_185
    assert stats["spread_bps"] == pytest.approx(15 / 60_185 * 10_000, abs=1e-3)
    assert stats["spread_abs"] == pytest.approx(15.0)
    assert "bps over BTCUSD" in out["read"]


def test_a_spread_is_a_difference_in_quote_units():
    out = synthetic.compose({"name": "ETH-BTC spread", "kind": "spread",
                             "legs": [{"symbol": "ETHUSDT", "side": 1},
                                      {"symbol": "BTCUSDT", "side": -1, "weight": 1}]},
                            {"ETHUSDT": series([3_000, 3_100, 3_200]),
                             "BTCUSDT": series([2_900, 2_950, 3_000])})
    assert out["stats"]["spread_abs"] == pytest.approx(200.0)
    assert out["stats"]["spread_bps"] == pytest.approx(200 / 3_000 * 10_000)


# ── the divergence statistics, on a fixture that can be checked by hand ────────────────────────

def test_the_z_score_and_the_share_beyond_sigma_match_a_hand_computation():
    # A spread of [1, 2, 3, 4, 5] against a flat leg: mean 3, population sigma sqrt(2).
    out = synthetic.compose({"name": "Ramp spread", "kind": "spread",
                             "legs": [{"symbol": "A", "side": 1}, {"symbol": "B", "side": -1}]},
                            {"A": series([11, 12, 13, 14, 15]), "B": series([10, 10, 10, 10, 10])},
                            {"min_samples": 3})
    stats = out["stats"]
    assert stats["samples"] == 5
    assert stats["mean"] == pytest.approx(3.0, abs=1e-6)
    assert stats["stdev"] == pytest.approx(math.sqrt(2.0), abs=1e-8)
    assert stats["z"] == pytest.approx(2 / math.sqrt(2.0), abs=1e-3)
    assert stats["beyond_stretch_pct"] == pytest.approx(40.0)     # the ends, |z| = 1.414
    assert stats["window_minutes"] == pytest.approx(4.0)
    zs = [point["z"] for point in out["series"]]
    assert [round(z, 4) for z in zs if z is not None] == [-1.4142, -0.7071, 0.0, 0.7071, 1.4142]
    assert out["stats"]["z"] == out["series"][-1]["z"]
    assert out["read"].endswith("over the last 4 minutes")


def test_a_composite_that_never_moved_reports_no_z_rather_than_a_zero():
    out = synthetic.compose({"name": "Flat basis", "kind": "basis",
                             "legs": [{"symbol": "A", "side": 1}, {"symbol": "B", "side": -1}]},
                            {"A": series([100, 100, 100]), "B": series([100, 100, 100])},
                            {"min_samples": 3})
    assert out["ok"] is True
    assert out["stats"]["z"] is None
    assert out["stats"]["z_reason"] == "flat"
    assert out["stats"]["beyond_stretch_pct"] is None
    assert "has not moved" in out["read"]


def test_too_few_samples_suppresses_the_z_score_and_says_so():
    out = synthetic.compose({"name": "Thin spread", "kind": "spread",
                             "legs": [{"symbol": "A", "side": 1}, {"symbol": "B", "side": -1}]},
                            {"A": series([11, 12, 13]), "B": series([10, 10, 10])},
                            {"min_samples": 40})
    assert out["stats"]["z"] is None
    assert out["stats"]["z_reason"] == "few"
    assert "no z-score yet" in out["read"]
    assert "need 40" in out["detail"]


def test_the_legs_correlation_and_the_carried_share_travel_with_the_read():
    out = synthetic.compose(ratio_def(),
                            {"ETHUSDT": series([3_000, 3_060, 3_120, 3_180, 3_240]),
                             "BTCUSDT": series([60_000, 60_600, 61_200, 61_800, 62_400])},
                            {"min_samples": 3})
    # Both legs move +2% per step, so their log returns are identical — a perfect correlation,
    # measured on returns rather than on the price levels.
    assert out["stats"]["correlation"] == pytest.approx(1.0)
    assert out["stats"]["correlation_pairs"] == 1
    assert out["stats"]["carried_pct"] == 0.0
    legs = {leg["symbol"]: leg for leg in out["legs"]}
    assert legs["ETHUSDT"]["samples"] == 5
    assert legs["BTCUSDT"]["carried_pct"] == 0.0
    assert out["settings"]["min_samples"] == 3


def test_carried_prices_are_reported_per_leg():
    out = synthetic.compose(basket_def(), {"BTCUSDT": series([60_000, 60_100, 60_200]),
                                           "ETHUSDT": [{"ts_ms": T0, "price": 3_000},
                                                       {"ts_ms": T0 + 2 * MINUTE, "price": 3_200}]},
                            {"min_samples": 3})
    legs = {leg["symbol"]: leg for leg in out["legs"]}
    assert legs["ETHUSDT"]["carried_pct"] == pytest.approx(100 / 3, abs=0.1)
    assert legs["BTCUSDT"]["carried_pct"] == 0.0
    assert out["stats"]["carried_pct"] == pytest.approx(50 / 3, abs=0.1)


# ── the refusals ───────────────────────────────────────────────────────────────────────────────

def test_a_leg_with_no_history_is_refused_by_name():
    out = synthetic.compose({"name": "BTC basis", "kind": "basis",
                             "legs": [{"symbol": "BTCUSDT", "side": 1},
                                      {"symbol": "BTCUSD", "side": -1}]},
                            {"BTCUSDT": series([60_000, 60_100, 60_200])})
    assert out["ok"] is False
    assert out["missing"] == ["BTCUSD"]
    assert out["detail"] == "no stored history for BTCUSD — open its chart first"


def test_a_composite_with_nothing_to_compose_is_refused_rather_than_guessed():
    empty = synthetic.compose(ratio_def(), {})
    assert empty["ok"] is False and "open its chart first" in empty["detail"]

    thin = synthetic.compose(ratio_def(), {"ETHUSDT": series([3_000, 3_100]),
                                           "BTCUSDT": series([60_000, 62_000])})
    assert thin["ok"] is False
    assert "at least 3" in thin["detail"]

    broken_denominator = synthetic.compose(
        ratio_def(),
        {"ETHUSDT": series([3_000, 3_100, 3_200]), "BTCUSDT": series([1.0, 1.0, 1.0])})
    assert broken_denominator["ok"] is True                # a 1.0 denominator is a valid ratio

    unusable = synthetic.compose({"name": "Nothing", "kind": "ratio", "legs": []},
                                 {"A": series([1, 2, 3])})
    assert unusable["ok"] is False
    assert "no usable legs" in unusable["detail"]


def test_read_sentence_shapes_match_the_house_voice():
    stats = {"spread_bps": 14.24, "z": 1.4, "z_stretch": 1.0, "reference_kind": "short_leg",
             "window_minutes": 240.0, "samples": 240}
    sentence = synthetic.read_sentence(
        {"name": "BTC perp", "kind": "basis",
         "legs": [{"symbol": "BTCUSDT", "side": 1}, {"symbol": "BTCUSD", "side": -1}]}, stats)
    assert sentence == "BTC perp is trading 14.2 bps over BTCUSD — 1.4 sigma rich over the last 4 hours"

    cheap = synthetic.read_sentence(
        {"name": "ETH/BTC ratio", "kind": "ratio",
         "legs": [{"symbol": "ETHUSDT", "side": 1}, {"symbol": "BTCUSDT", "side": -1}]},
        {"spread_bps": -3.5, "z": -2.2, "reference_kind": "window_median", "window_minutes": 60.0})
    assert cheap == ("ETH/BTC ratio is trading 3.5 bps below its 1-hour median — 2.2 sigma cheap "
                     "over the last 1 hour")

    flat = synthetic.read_sentence(
        {"name": "Flat", "kind": "basket", "legs": [{"symbol": "A", "side": 1}]},
        {"spread_bps": 0.05, "z": 0.1, "reference_kind": "window_median", "window_minutes": 30.0})
    assert "flat, 0.1 sigma" in flat
    assert synthetic.human_window(1440) == "1 day"
    assert synthetic.human_window(240, hyphen=True) == "4-hour"
    assert synthetic.human_window(None) == "the window"


# ── the routes ─────────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def store(tmp_path, monkeypatch):
    """The config store pointed at a temp directory — never the user's real config."""
    from orderflow_system.desktop import config_store
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


@pytest.fixture()
def client(store):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(synthetic.router)
    return TestClient(app)


def test_the_router_declares_the_three_routes_the_panel_calls():
    paths = {(route.path, method) for route in synthetic.router.routes
             for method in getattr(route, "methods", set())}
    assert ("/api/atlas/synthetic", "GET") in paths
    assert ("/api/atlas/synthetic/compose", "GET") in paths
    assert ("/api/atlas/synthetic", "POST") in paths
    assert synthetic.router.prefix == "/api/atlas"


def test_the_list_route_answers_with_the_starters_even_with_no_engine(client, monkeypatch):
    monkeypatch.setattr(synthetic, "_engine_system", lambda: None)
    payload = client.get("/api/atlas/synthetic").json()
    assert payload["ok"] is True
    assert [d["id"] for d in payload["definitions"]] == list(synthetic.STARTER_IDS)
    assert payload["symbols"] and all({"symbol", "live", "history"} <= set(s) for s in payload["symbols"])
    assert payload["settings"]["window_min"] == synthetic.DEFAULTS["window_min"]
    assert payload["kinds"] == list(synthetic.KINDS)


def test_the_compose_route_refuses_with_a_sentence_and_never_a_500(client, monkeypatch):
    monkeypatch.setattr(synthetic, "_engine_system", lambda: None)
    stopped = client.get("/api/atlas/synthetic/compose?definition=eth-btc-ratio")
    assert stopped.status_code == 200
    body = stopped.json()
    assert body["ok"] is False and "engine is not running" in body["detail"]

    unknown = client.get("/api/atlas/synthetic/compose?definition=nope").json()
    assert unknown["ok"] is False and "no synthetic instrument called" in unknown["detail"]

    unnamed = client.get("/api/atlas/synthetic/compose").json()
    assert unnamed["ok"] is False and "name a synthetic instrument" in unnamed["detail"]


def test_the_compose_route_composes_from_the_legs_it_can_read(client, monkeypatch):
    """The engine is stubbed at the two seams the route owns: its system object and its store."""
    prices = {"ETHUSDT": [3_000, 3_060, 3_120, 3_180, 3_240, 3_300],
              "BTCUSDT": [60_000, 60_600, 61_200, 61_800, 62_400, 63_000]}

    async def fake_rows(symbol: str, start_ms: int, end_ms: int):
        return [(T0 + index * MINUTE, float(price))
                for index, price in enumerate(prices.get(symbol, []))]

    monkeypatch.setattr(synthetic, "_engine_system", lambda: object())
    monkeypatch.setattr(synthetic, "_stored_rows", fake_rows)
    body = client.get("/api/atlas/synthetic/compose?definition=eth-btc-ratio&window_min=60").json()
    assert body["ok"] is True
    assert body["definition"]["id"] == "eth-btc-ratio"
    assert body["stats"]["samples"] == 6
    assert body["stats"]["value"] == pytest.approx(3_300 / 63_000)
    assert body["window_min"] == 60
    assert body["at_ms"] > 0
    assert "bps" in body["read"]
    assert len(body["series"]) == 6 and {"t", "v", "z"} == set(body["series"][0])

    # A leg the store cannot answer is the refusal the panel shows, not a zero-filled series.
    async def half_rows(symbol: str, start_ms: int, end_ms: int):
        return [(T0, 1.0), (T0 + MINUTE, 2.0)] if symbol == "ETHUSDT" else []

    monkeypatch.setattr(synthetic, "_stored_rows", half_rows)
    refused = client.get("/api/atlas/synthetic/compose?definition=eth-btc-ratio").json()
    assert refused["ok"] is False
    assert refused["detail"] == "no stored history for BTCUSDT — open its chart first"


def test_the_post_route_validates_stores_and_answers_with_the_accepted_definition(client, store):
    accepted = client.post("/api/atlas/synthetic", json={
        "name": "SOL/BTC ratio", "kind": "ratio",
        "legs": [{"symbol": "SOLUSDT", "side": 1}, {"symbol": "BTCUSDT", "side": -1}]})
    body = accepted.json()
    assert body["ok"] is True and body["saved"] is True
    assert body["definition"]["id"] == "sol-btc-ratio"
    assert [d["id"] for d in body["definitions"]][-1] == "sol-btc-ratio"

    # It is really in the store, and the next read composes it by that id.
    stored = store.load_config()["atlas"]["synthetic"]["definitions"]
    assert "sol-btc-ratio" in [d["id"] for d in stored]
    listed = client.get("/api/atlas/synthetic").json()
    assert "sol-btc-ratio" in [d["id"] for d in listed["definitions"]]

    # The same id replaces rather than duplicates — a rename is an edit, not a second instrument.
    again = client.post("/api/atlas/synthetic", json={
        "id": "sol-btc-ratio", "name": "SOL/BTC ratio", "kind": "ratio",
        "legs": [{"symbol": "SOLUSDT", "side": 1, "weight": 2},
                 {"symbol": "BTCUSDT", "side": -1}]}).json()
    assert [d["id"] for d in again["definitions"]].count("sol-btc-ratio") == 1

    refused = client.post("/api/atlas/synthetic", json={"name": "Broken", "kind": "ratio",
                                                        "legs": []}).json()
    assert refused["ok"] is False
    assert refused["problems"] and "at least one leg" in refused["detail"]


def test_the_post_route_accepts_a_definition_wrapped_in_an_object(client, store):
    wrapped = client.post("/api/atlas/synthetic",
                          json={"definition": {"name": "Wrap test", "kind": "basket",
                                               "legs": [{"symbol": "BTCUSDT", "side": 1}]}}).json()
    assert wrapped["ok"] is True
    assert wrapped["definition"]["id"] == "wrap-test"
    assert wrapped["definition"]["kind"] == "basket"


def test_the_route_reads_a_real_candle_store_through_the_engines_own_database(client, monkeypatch,
                                                                              tmp_path):
    """The route's own seam, end to end: a real Database, real 1-minute candles, and the engine
    stubbed only where the route reaches for it (the system object). This is the read the panel
    performs in the app — the composition itself is the pure half, already covered above."""
    asyncio.run(_candle_store_scenario(client, monkeypatch, tmp_path))


async def _candle_store_scenario(client, monkeypatch, tmp_path):
    from orderflow_system.data.database import Database
    from orderflow_system.data.models import Candle

    # Candles near NOW, a minute apart, because the route windows the store around the wall clock.
    newest = int(time.time() * 1000)
    newest -= newest % MINUTE
    db = Database(str(tmp_path / "synthetic-fixture.db"))
    await db.connect()
    try:
        for symbol, base in (("ETHUSDT", 3_000.0), ("BTCUSDT", 60_000.0)):
            for step in range(6):
                moment = newest - (5 - step) * MINUTE
                close = base + step
                await db.insert_candle(symbol, "1m", Candle(
                    timestamp_ms=moment, open=close - 0.5, high=close + 0.5, low=close - 1.0,
                    close=close, volume=1.0))

        class StubSystem:
            """Just the two attributes the route touches: the database and the pipelines map."""

        system = StubSystem()
        system.db = db
        system.pipelines = {}
        monkeypatch.setattr(synthetic, "_engine_system", lambda: system)

        body = client.get("/api/atlas/synthetic/compose"
                          "?definition=eth-btc-ratio&window_min=60&points=100").json()
        assert body["ok"] is True, body
        assert body["stats"]["samples"] == 6
        assert body["stats"]["value"] == pytest.approx(3_005 / 60_005, abs=1e-8)
        assert [leg["samples"] for leg in body["legs"]] == [6, 6]
        assert body["stats"]["carried_pct"] == 0.0
        assert "bps" in body["read"]

        # One leg with candles and one without is the refusal the panel prints, from the real read.
        refused = client.get("/api/atlas/synthetic/compose?definition=btc-perp-basis").json()
        assert refused["ok"] is False
        assert refused["detail"] == "no stored history for BTCUSD — open its chart first"
    finally:
        await db.close()


def test_the_pure_module_never_reaches_for_the_engine():
    """The composition functions must stay offline: no config, no database, no hub."""
    import inspect
    for name in ("compose", "align", "premium", "composite_value", "read_sentence", "clean",
                 "check_definition", "clean_definition"):
        source = inspect.getsource(getattr(synthetic, name))
        for banned in ("config_store", "get_candles", "engine", "requests", "aiohttp"):
            assert banned not in source, f"{name} touches {banned}"


# ── §148 T4-F4: the leg weight is capped at the panel's own maximum ─────────────────────────────

def test_a_leg_weight_is_capped_at_the_panels_own_maximum():
    """The weight input says max="1000"; a weight above it must not overflow the arithmetic.

    Measured before the fix: `normalise_leg` accepted 1e300, `check_definition` stored it, and
    GET /api/atlas/synthetic/compose answered 500 (stdev squares the weighted values) while the
    route's own docstring promises "never a 500".
    """
    assert synthetic.normalise_leg({"symbol": "A", "weight": 1e300})["weight"] == synthetic.LEG_WEIGHT_MAX
    assert synthetic.normalise_leg({"symbol": "A", "weight": 1e308})["weight"] == synthetic.LEG_WEIGHT_MAX
    assert synthetic.normalise_leg({"symbol": "A", "weight": 1000})["weight"] == 1000.0, "the boundary stands"
    assert synthetic.normalise_leg({"symbol": "A", "weight": 1000.5})["weight"] == 1000.0, "the cap clamps"
    assert synthetic.normalise_leg({"symbol": "A", "weight": -4})["weight"] == -4.0, "a readable weight passes through"
    assert synthetic.normalise_leg({"symbol": "A", "weight": "junk"})["weight"] == 0.0, "an unreadable one reads as 0"
    _, negative = synthetic.check_definition(
        {"name": "X", "kind": "spread",
         "legs": [{"symbol": "A", "side": 1, "weight": -4}, {"symbol": "B", "side": -1}]})
    assert negative and "weight is -4" in negative[0], "the validator still refuses it by name"
    definition, problems = synthetic.check_definition(
        {"name": "Big", "kind": "ratio",
         "legs": [{"symbol": "A", "side": 1, "weight": 1e300}, {"symbol": "B", "side": -1, "weight": 1}]})
    assert problems == [] and definition is not None
    assert definition["legs"][0]["weight"] == synthetic.LEG_WEIGHT_MAX
    series = {"A": [{"ts_ms": 60_000 * i, "price": 100 + i} for i in range(10)],
              "B": [{"ts_ms": 60_000 * i, "price": 50 + i} for i in range(10)]}
    payload = synthetic.compose({"name": "Big", "kind": "ratio",
                                 "legs": [{"symbol": "A", "side": 1, "weight": 1e300},
                                          {"symbol": "B", "side": -1, "weight": 1}]}, series)
    assert payload["ok"] is True, payload.get("detail")


# ── §148 T4-F8/F9: the full store, and the JS half's own gate ───────────────────────────────────

UI = Path(__file__).resolve().parents[1] / "orderflow_system" / "desktop" / "ui"
SYNTHETIC_JS = UI / "synthetic.js"
SYNTHETIC_SELFTEST = UI / "synthetic.selftest.js"


def test_a_full_store_refuses_the_25th_rather_than_evicting_one(client, store):
    """§148 T4-F8 — a save past the cap dropped the oldest definition while answering "saved"."""
    stored = (store.load_config() or {}).get("atlas", {}).get("synthetic")
    existing = len(synthetic.clean(stored)["definitions"])       # the starter definitions ship here
    for index in range(synthetic.MAX_DEFINITIONS - existing):
        answer = client.post("/api/atlas/synthetic",
                             json=ratio_def(name=f"Ratio {index:02d}")).json()
        assert answer["saved"] is True and answer["ok"] is True, answer
    ids = [item["id"] for item in store.load_config()["atlas"]["synthetic"]["definitions"]]
    assert len(ids) == synthetic.MAX_DEFINITIONS and "ratio-00" in ids

    refused = client.post("/api/atlas/synthetic", json=ratio_def(name="One too many")).json()
    assert refused["ok"] is True, "the definition itself is fine — the store is what is full"
    assert refused["saved"] is False
    assert "delete one before saving another" in refused["detail"]
    after = [item["id"] for item in store.load_config()["atlas"]["synthetic"]["definitions"]]
    assert after == ids, "nothing was evicted for the refusal"

    # and an edit of a stored definition still lands while the store is full
    edited = client.post("/api/atlas/synthetic",
                         json=ratio_def(id="ratio-00", name="Ratio renamed")).json()
    assert edited["saved"] is True, edited


def test_the_panel_offers_every_kind_and_cap_the_server_can_take():
    """§148 T4-F9 — the panel's tables were pinned only against themselves: a kind added in Python
    would leave the builder unable to offer it with every test still green."""
    text = SYNTHETIC_JS.read_text(encoding="utf-8", errors="replace")
    found = re.search(r"const KINDS = \[([^\]]*)\]", text)
    assert found, "synthetic.js lost its KINDS table"
    assert tuple(re.findall(r"'([a-z]+)'", found.group(1))) == tuple(synthetic.KINDS), \
        "the panel's kinds drifted from atlas/synthetic.py"
    assert f"const MAX_LEGS = {synthetic.MAX_LEGS};" in text, "the two leg caps drifted"
    windows = re.search(r"const WINDOWS = \[([^\]]*)\]", text)
    assert windows, "synthetic.js lost its WINDOWS table"
    low, high = synthetic._WINDOW_BOUNDS
    for minutes in re.findall(r"\d+", windows.group(1)):
        assert low <= int(minutes) <= high, f"window {minutes} is outside the server's bounds"


def test_the_synthetic_selftest_runs_and_passes():
    """§148 T4-F9 — the JS half was never executed by the gate; sessions' twin ran from pytest."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    proc = subprocess.run([node, str(SYNTHETIC_SELFTEST)], capture_output=True, text=True,
                          encoding="utf-8", timeout=60)
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    found = re.search(r"synthetic selftest: (\d+) ok, (\d+) failed", out)
    assert found, f"the selftest printed no verdict:\n{out}"
    assert found.group(2) == "0"
    assert int(found.group(1)) >= 17, f"only {found.group(1)} checks ran — the selftest shrank"
