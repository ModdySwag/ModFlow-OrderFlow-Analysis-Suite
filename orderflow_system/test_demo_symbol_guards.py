"""The demo-fill guard, generalised to every endpoint that takes a symbol (§68).

v0.1b Tier 8 #2 fixed /api/footprint and /api/tape: with no engine running, an UNKNOWN
symbol gets nothing — not the old invented $1,000 fiction. The same rule belongs to the
rest of the demo fillers the desktop shell polls, because the shell clones the active
symbol across every panel: markers, candles, volume-profile, delta, bias, orderbook,
strategy-status and microstructure. A symbol the demo generator does not model
(demo_data.models_symbol) must come back empty-of-the-right-shape from all of them —
while every MODELED symbol keeps its demo fill unchanged.

This file is the receipt that the rule holds everywhere, and that nothing else moved:
the second test pins each modeled path end to end.
"""

from __future__ import annotations

UNKNOWN = "UNKNOWNXYZ"  # not in _BASE_PRICES — the generator must refuse it
MODELED = "BTCUSDT"     # a modeled symbol — the demo fill must keep working


def _client():
    from fastapi.testclient import TestClient

    # build_app() may run once per process; test_wiring owns the shared singleton
    # (see its _desktop_app docstring) — importing it here keeps that invariant.
    from orderflow_system.test_wiring import _desktop_app

    return TestClient(_desktop_app())


def test_unknown_symbols_serve_nothing_from_every_demo_filler():
    """Every demo filler must stay silent for a symbol the generator does not model.

    Measured before this guard existed: each of these eight endpoints answered an unknown
    symbol with a plausible-looking fiction (a chart, a book, a bias, a checklist) —
    the same class of defect Tier 8 #2 fixed for footprint/tape, in eight more places.
    """
    client = _client()

    assert client.get(f"/api/markers/{UNKNOWN}").json() == [], "no invented markers"
    assert client.get(f"/api/candles/{UNKNOWN}").json() == [], "no invented candles"
    assert client.get(f"/api/volume-profile/{UNKNOWN}").json() == [], "no invented profile"
    assert client.get(f"/api/delta/{UNKNOWN}").json() == [], "no invented delta series"

    bias = client.get(f"/api/bias/{UNKNOWN}").json()
    assert bias["direction"] == "neutral" and bias["confidence"] == 0, bias
    assert bias["qualified_levels"] == [], "no invented qualified levels"
    assert bias["source"] == "demo", "the empty stays tagged to its branch"

    status = client.get(f"/api/strategy-status/{UNKNOWN}").json()
    assert status["overall"] == "OFFLINE" and status["steps"] == [], "no invented checklist"
    assert status["trade"] is None and status["source"] == "demo"

    book = client.get(f"/api/orderbook/{UNKNOWN}").json()
    assert book["bids"] == [] and book["asks"] == [], "no invented book"
    assert book["imbalance"] == 0.0 and book["source"] == "demo"

    micro = client.get(f"/api/microstructure/{UNKNOWN}").json()
    assert micro["patterns"] == [] and micro["exhaustion"] == 0, "no invented patterns"
    assert micro["delta"]["cumulative"] == 0 and micro["source"] == "demo"


def test_modeled_symbols_keep_their_demo_fills_across_every_endpoint():
    """The other half of the contract: for a symbol the generator models, every fill the
    demo tour relies on is still there, non-empty, after the guard pass."""
    client = _client()

    assert len(client.get(f"/api/markers/{MODELED}").json()) > 0
    assert len(client.get(f"/api/candles/{MODELED}").json()) > 0
    assert len(client.get(f"/api/volume-profile/{MODELED}").json()) > 0
    assert len(client.get(f"/api/delta/{MODELED}").json()) > 0

    bias = client.get(f"/api/bias/{MODELED}").json()
    assert bias["direction"] in ("long", "short", "neutral")
    assert len(bias["qualified_levels"]) > 0, "modeled symbols keep their demo levels"
    assert bias["source"] == "demo"

    status = client.get(f"/api/strategy-status/{MODELED}").json()
    assert status["overall"] != "OFFLINE" and len(status["steps"]) > 0
    assert status["source"] == "demo"

    book = client.get(f"/api/orderbook/{MODELED}").json()
    assert len(book["bids"]) > 0 and len(book["asks"]) > 0
    assert book["source"] == "demo"

    micro = client.get(f"/api/microstructure/{MODELED}").json()
    assert len(micro["patterns"]) > 0 and micro["source"] == "demo"
