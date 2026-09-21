"""orders: the account drivers, the risk gates and the one door an order leaves by.

Offline throughout: the paper driver is exercised on a 0.25-tick future with hand-fed prints, and
the live path is exercised by proving it *cannot* fill. What this file pins:

  * the settings block coerces, and ``live_disabled`` can only be turned off on purpose
  * the bridge refuses every method with one sentence, and never answers ``ok`` or an order row
  * the router runs its gates in order — size, max size, the day's loss, concurrent positions
  * a routed order reaches the paper account with its template intact, so the bracket is armed
  * the route table points at routes this build actually serves
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orderflow_system.atlas import api as atlas_api
from orderflow_system.desktop import atm, orders
from orderflow_system.desktop.orders import BridgeDriver, OrderRouter, PaperDriver
from orderflow_system.desktop.paper import PaperAccount

TICK = 0.25
SYMBOL = "ESZ6"


def account(balance: float = 100_000.0, **kwargs) -> PaperAccount:
    return PaperAccount(symbol=SYMBOL, tick_size=TICK, starting_balance=balance, **kwargs)


def filled(account_: PaperAccount, side: str, size: float, price: float, ts_ms: int = 1_000,
           **kwargs) -> PaperAccount:
    """Submit a market order and drive the one print that fills it — the next print."""
    account_.submit(side, size, ts_ms=ts_ms - 1, **kwargs)
    account_.on_trade(price, size, "sell" if side == "buy" else "buy", ts_ms)
    return account_


def losing_round_trip(account_: PaperAccount, ticks: float = 12.0) -> PaperAccount:
    """Bank a loss of ``ticks`` paper ticks: in, out, journal row."""
    move = ticks * TICK
    filled(account_, "buy", 1, 5000.0, ts_ms=1_000)
    filled(account_, "sell", 1, 5000.0 - move, ts_ms=2_000)
    return account_


# ══════════════════════════════════════════════════════════════
# The settings block
# ══════════════════════════════════════════════════════════════

def test_the_defaults_are_paper_and_live_is_off():
    assert orders.DEFAULTS == {"driver": "paper", "live_disabled": True, "max_size": 0.0,
                               "max_positions": 1, "daily_loss_cap_ticks": 0.0}
    assert orders.clean(None) == orders.DEFAULTS
    assert orders.clean("nonsense") == orders.DEFAULTS
    assert orders.clean({"unknown": 1}) == orders.DEFAULTS


def test_clean_clamps_the_caps_and_never_turns_live_on_by_accident():
    assert orders.clean({"driver": "BRIDGE"})["driver"] == "bridge"
    assert orders.clean({"driver": "binance"})["driver"] == "paper"        # unknown driver: paper
    assert orders.clean({"max_size": -5})["max_size"] == 0.0               # 0 means "no cap"
    assert orders.clean({"max_size": "3.5"})["max_size"] == 3.5
    assert orders.clean({"max_size": "abc"})["max_size"] == 0.0
    assert orders.clean({"max_positions": 3.7})["max_positions"] == 3
    assert orders.clean({"max_positions": 500})["max_positions"] == 100    # a hundred is the ceiling
    assert orders.clean({"daily_loss_cap_ticks": "-40"})["daily_loss_cap_ticks"] == 0.0
    assert orders.clean({"daily_loss_cap_ticks": "40"})["daily_loss_cap_ticks"] == 40.0
    # Live is only ever cleared by an explicit false: a string, a missing key or a junk value all
    # leave the switch ON — the safe reading of "I am not sure" is "live is off".
    assert orders.clean({})["live_disabled"] is True
    assert orders.clean({"live_disabled": "no"})["live_disabled"] is True
    assert orders.clean({"live_disabled": 0})["live_disabled"] is True
    assert orders.clean({"live_disabled": None})["live_disabled"] is True
    assert orders.clean({"live_disabled": False})["live_disabled"] is False


def test_the_route_table_names_the_routes_this_build_serves():
    """The router reports where an order goes; those paths must be real routes, not wishes."""
    source = Path(atlas_api.__file__).read_text(encoding="utf-8")
    for what, path in orders.ROUTES["paper"].items():
        assert path.startswith("/api/atlas/replay/paper/"), what
        assert f'"{path.replace("/api/atlas", "")}"' in source, f"{what} route {path} is not served"
    assert orders.ROUTES["bridge"] == {}
    router = OrderRouter(settings={"driver": "bridge"})
    assert router.route_for("order") is None and router.route_for("nope") is None
    assert OrderRouter().route_for("order") == "/api/atlas/replay/paper/order"


def test_a_ladder_shaped_body_reaches_the_paper_route_with_its_plan_armed(monkeypatch):
    """§148: the ladder posts its plan-bar template as an OBJECT; the route must not stringify it.

    Live, before the fix: `str(body["template"])` turned the template into a Python repr,
    `_resolve_template` read that as an unknown template id, and every planned order the ladder
    could place came back rejected — while the router-level pin above (which hands the driver a
    dict directly) stayed green. This drives the route the ladder actually posts to.
    """
    import time as _time

    monkeypatch.setattr(orders, "_stored", lambda key: None)     # the shipped defaults, hermetic
    saved_paper = dict(atlas_api._paper)
    saved_router = orders._SESSION.get("router")
    app = FastAPI()
    app.include_router(atlas_api.router)
    client = TestClient(app)
    try:
        started = client.post("/api/atlas/replay/paper/start",
                              json={"symbol": SYMBOL, "tick_size": TICK}).json()
        assert started["ok"] is True
        plan = {"id": "runner", "name": "Runner", "size": 1.0, "stop_ticks": 8,
                "target_ticks": 16, "breakeven_ticks": 6, "time_stop_min": 30}
        answer = client.post("/api/atlas/replay/paper/order",
                             json={"side": "buy", "size": 1, "kind": "market",
                                   "template": plan}).json()
        assert answer["ok"] is True, answer.get("error")
        assert answer["order"]["status"] == "working", answer["order"].get("reason")
        assert (answer["order"].get("plan_template") or {}).get("id") == "runner"
        account = atlas_api._paper["account"]
        account.on_trade(4500.0, 1.0, "sell", int(_time.time() * 1000) + 1000)
        state = client.get("/api/atlas/replay/paper/state").json()["state"]
        assert state["plan"] and state["plan"]["status"] == "live", state["plan"]
    finally:
        atlas_api._paper.clear()
        atlas_api._paper.update(saved_paper)
        orders._SESSION["router"] = saved_router


def test_the_paper_session_binds_the_router_and_its_gates_refuse_on_the_route(monkeypatch):
    """§148: /replay/paper/start binds the session router, and its gates refuse through the route.

    Measured before the fix: `bind_account` had zero production callers and this route handed the
    order straight to the account, so `max_size`, the day's loss cap, the concurrent-position limit
    and the bridge refusal could never fire for an order a user placed.
    """
    monkeypatch.setattr(orders, "_stored",
                        lambda key: {"driver": "paper", "max_size": 0.5} if key == "orders" else None)
    saved_paper = dict(atlas_api._paper)
    saved_router = orders._SESSION.get("router")
    app = FastAPI()
    app.include_router(atlas_api.router)
    client = TestClient(app)
    try:
        assert client.post("/api/atlas/replay/paper/start",
                           json={"symbol": SYMBOL, "tick_size": TICK}).json()["ok"] is True
        bound = orders.session_router()
        assert bound is not None, "the session left no router bound"
        assert bound.account is atlas_api._paper["account"]
        assert bound.settings["max_size"] == 0.5
        answer = client.post("/api/atlas/replay/paper/order",
                             json={"side": "buy", "size": 1, "kind": "market"}).json()
        assert answer["ok"] is False
        assert answer["gate"] == "max_size", answer.get("gate")
        assert "max size" in answer["error"], answer["error"]
        # the refusal still takes an id and a row: the session's ledger keeps the trace
        assert answer["order"]["status"] == "rejected"
        assert "max size" in answer["order"]["reason"]
        assert answer["order"]["id"] == "o1"
        state = client.get("/api/atlas/replay/paper/state").json()["state"]
        assert state["orders"] == [] and state["position"]["side"] == "flat"
        assert state["stats"]["orders_rejected"] == 1
        closed = client.post("/api/atlas/replay/paper/close").json()
        assert closed["ok"] is True
        assert orders.session_router() is None, "the router outlived the session"
    finally:
        atlas_api._paper.clear()
        atlas_api._paper.update(saved_paper)
        orders._SESSION["router"] = saved_router


# ══════════════════════════════════════════════════════════════
# The drivers
# ══════════════════════════════════════════════════════════════

def test_the_paper_driver_hands_the_order_to_the_account():
    account_ = account()
    driver = PaperDriver(account_)
    assert driver.name == "paper"
    result = driver.submit("buy", 2, kind="market", price=None, stop_loss=None, take_profit=None,
                           template=None, ts_ms=10)
    assert result["ok"] is True and result["status"] == "working"
    assert result["order"]["id"] == "o1" and result["order"]["size"] == 2.0
    driver.submit("sell", 1, kind="limit", price=5050.0, ts_ms=20)
    driver.submit("sell", 1, kind="limit", price=5060.0, ts_ms=25)
    assert [o["id"] for o in account_.open_orders()] == ["o1", "o2", "o3"]

    assert driver.cancel("o2") is True and driver.cancel("o2") is False
    account_.on_trade(5000.0, 1, "sell", 30)                      # the market order fills here
    assert driver.position()["side"] == "long" and driver.position()["size"] == 2.0
    assert driver.cancel_all() == ["o3"]
    assert driver.flatten(5001.0, 40)[0]["reason"] == "flatten"
    assert driver.position()["side"] == "flat"
    assert driver.flatten(5001.0, 50) == []                    # nothing left to close
    state = driver.state()
    assert state["ok"] is True and state["symbol"] == SYMBOL and state["stats"]["orders_submitted"] == 3
    assert state["stats"]["orders_filled"] == 1


def test_the_paper_driver_refuses_with_a_sentence_instead_of_an_account():
    driver = PaperDriver(None)
    result = driver.submit("buy", 1, ts_ms=1)
    assert result == {"ok": False, "status": "rejected", "reason": orders.NO_ACCOUNT_REFUSAL,
                      "order": None}
    assert driver.cancel("o1") is False and driver.cancel_all() == []
    assert driver.flatten(5000.0, 1) == []
    assert driver.position()["side"] == "flat" and driver.stats() == {}
    assert driver.state() == {"ok": False, "reason": orders.NO_ACCOUNT_REFUSAL}


def test_the_bridge_refuses_every_method_and_never_invents_a_fill():
    driver = BridgeDriver()
    assert driver.name == "bridge" and driver.reason == orders.BRIDGE_REFUSAL
    result = driver.submit("buy", 1, kind="market", price=None, stop_loss=None, take_profit=None,
                           template="scalp", ts_ms=1)
    assert result == {"ok": False, "status": "refused", "reason": orders.BRIDGE_REFUSAL, "order": None}
    assert driver.cancel("o1") is False and driver.cancel_all() == [] and driver.flatten(5000.0, 1) == []
    assert driver.position()["side"] == "flat"
    state = driver.state()
    assert state["ok"] is False and state["reason"] == orders.BRIDGE_REFUSAL
    # There is no account to fall back on: a bridge that filled would be a simulated live trade.
    assert not hasattr(driver, "account")


def test_the_live_refusals_are_one_plain_sentence_each():
    assert orders.LIVE_REFUSAL == ("live routing is off — this build has no broker connection, so "
                                   "orders only ever reach the paper account")
    assert orders.BRIDGE_REFUSAL == ("no live account is configured in this build — a live order is "
                                     "refused here rather than filled")
    assert "no paper session" in orders.NO_ACCOUNT_REFUSAL
    assert orders.NO_SESSION_REFUSAL.startswith("no trading session is bound here yet")


# ══════════════════════════════════════════════════════════════
# The gates
# ══════════════════════════════════════════════════════════════

def test_the_gate_table_reports_every_gate_in_order():
    router = OrderRouter(account())
    verdicts = router.gates("buy", 1)
    assert [v["gate"] for v in verdicts] == ["driver", "size", "max_size", "daily_loss_cap",
                                            "max_positions"]
    assert all(v["ok"] for v in verdicts) and all(v["detail"] == "" for v in verdicts)
    assert router.check("buy", 1) == {"gate": "", "reason": ""}
    json.dumps(verdicts)


def test_size_must_be_a_positive_number():
    router = OrderRouter(account())
    for size in (0, -3, "abc", None):
        result = router.route("buy", size)
        assert result["ok"] is False and result["gate"] == "size"
        assert result["reason"] == orders.SIZE_REFUSAL and result["order"] is None
    assert router.account.stats()["orders_submitted"] == 0        # nothing reached the account


def test_max_size_refuses_what_is_past_it_and_allows_what_is_not():
    router = OrderRouter(account(), settings={"max_size": 2})
    big = router.route("buy", 3)
    assert big["ok"] is False and big["gate"] == "max_size"
    assert big["reason"] == "order refused: size 3 is past the max size 2 in Risk settings"
    assert router.account.stats()["orders_submitted"] == 0
    assert router.route("buy", 2)["ok"] is True
    assert router.route("buy", 2.5)["reason"].startswith("order refused: size 2.5 is past the max size 2")


def test_the_daily_loss_cap_stops_the_day_and_a_new_baseline_starts_it():
    account_ = account()
    router = OrderRouter(account_, settings={"daily_loss_cap_ticks": 10})
    assert router.day_ticks() == 0.0
    # a resting order, so the check leaves no print behind to interfere with the loss below
    assert router.route("buy", 1, kind="limit", price=4000.0)["ok"] is True
    losing_round_trip(account_, ticks=12.0)
    assert router.session_ticks() == -12.0 and router.day_ticks() == -12.0

    stopped = router.route("buy", 1)
    assert stopped["ok"] is False and stopped["gate"] == "daily_loss_cap"
    assert stopped["reason"] == ("order refused: the daily loss cap of 10 ticks has been reached "
                                 "(the day stands at -12)")
    # the cap is measured from the day's baseline, so a new day starts with a clean slate
    assert router.start_day("2026-09-21", ticks_now=router.session_ticks()) == {
        "ok": True, "day": "2026-09-21", "baseline_ticks": -12.0}
    assert router.day_ticks() == 0.0
    assert router.route("buy", 1, kind="limit", price=4000.0)["ok"] is True
    assert router.status()["day"] == "2026-09-21"
    # ...and a cap of 0 means "no cap configured", not "no loss allowed"
    assert OrderRouter(account_, settings={"daily_loss_cap_ticks": 0}).route("buy", 1)["ok"] is True


def test_max_concurrent_positions_refuses_a_new_position_but_not_a_reducing_order():
    """The cap counts *positions*, so it blocks an order that would open one on a flat account and
    lets through anything that reduces a position already open."""
    first, second, third = account(), account(), account()
    router = OrderRouter(first)                                    # DEFAULTS: max_positions 1
    router.attach(second)
    router.attach(third)
    assert router.open_positions() == 0
    assert router.route("buy", 1, kind="limit", price=4000.0)["ok"] is True   # rests: no print, no fill
    filled(first, "buy", 1, 5000.0, ts_ms=1_000)
    assert router.open_positions() == 1

    blocked = router.route("buy", 1, account=second)               # a new position, flat account
    assert blocked["ok"] is False and blocked["gate"] == "max_positions"
    assert blocked["reason"] == "order refused: 1 position is open and max concurrent positions is 1"
    assert router.check("buy", 1, account=second)["gate"] == "max_positions"
    assert router.route("sell", 1)["ok"] is True                   # reducing the position is fine
    assert router.route("buy", 1)["ok"] is True                    # and so is adding to it

    two = OrderRouter(settings={"max_positions": 2})
    two.attach(first)
    two.attach(second)
    two.attach(third)
    assert two.open_positions() == 1
    assert two.route("buy", 1, account=second, kind="limit", price=4000.0)["ok"] is True
    filled(second, "buy", 1, 5001.0, ts_ms=2_000)
    assert two.open_positions() == 2
    assert two.route("buy", 1, account=third)["gate"] == "max_positions"
    # a router with no cap configured lets the third position through
    unlimited = OrderRouter(settings={"max_positions": 0})
    unlimited.attach(first)
    unlimited.attach(second)
    unlimited.attach(third)
    assert unlimited.route("buy", 1, account=third, kind="limit", price=4000.0)["ok"] is True
    assert OrderRouter().open_positions() == 0 and OrderRouter().session_ticks() == 0.0


def test_attaching_another_account_does_not_rebase_the_day():
    """§148 T1-D10: ``attach`` cleared the baseline the caller had just set, so the loss cap started
    counting PnL the caller had explicitly rebased away. Only ``set_account``/``start_day`` rebase."""
    first = account()
    router = OrderRouter(first, settings={"daily_loss_cap_ticks": 10})
    losing_round_trip(first, ticks=12.0)
    router.start_day("2026-09-21", ticks_now=router.session_ticks())
    assert router.day_ticks() == 0.0

    router.attach(account())                              # a second session joins the same day
    assert router.day_ticks() == 0.0                       # the baseline the caller set stands
    assert router.route("buy", 1, kind="limit", price=4000.0)["ok"] is True

    # set_account is the one that starts a fresh day: the baseline goes with the old session
    second = account()
    router.set_account(second)
    losing_round_trip(second, ticks=5.0)
    assert router.day_ticks() == -5.0        # measured from the new session, not the old baseline


def test_the_position_cap_counts_positions_never_entries_on_one_account():
    """§148 T1-D3: the shipped cap refuses an order that would open a position while the attached
    accounts already hold the cap's worth — nothing else. Entries resting on an account are not
    positions, and this build's single trading account holds at most one position at a time, so the
    cap cannot refuse its own orders: two resting entries on that account are both allowed. The
    refusal needs a caller that attached more than one account — the case pinned above.

    The DEFAULTS sentence now says exactly this; before, it promised a refusal the app cannot reach.
    """
    acc = account()
    router = OrderRouter(acc)                                     # DEFAULTS: max_positions 1
    assert router.route("buy", 1, kind="limit", price=4000.0)["ok"] is True
    assert router.route("sell", 1, kind="limit", price=5050.0)["ok"] is True  # entries are not positions
    assert router.open_positions() == 0 and len(acc.open_orders()) == 2

    # a held position lets adds and reduces through: neither opens anything
    filled(acc, "buy", 1, 5000.0, ts_ms=1_000)
    assert router.open_positions() == 1
    assert router.route("buy", 1)["ok"] is True
    assert router.route("sell", 1)["ok"] is True


def test_routing_without_an_account_refuses_before_anything_else():
    router = OrderRouter(settings={"max_size": 1})
    result = router.route("buy", 99)
    assert result["ok"] is False and result["gate"] == "account"
    assert result["reason"] == orders.NO_ACCOUNT_REFUSAL
    assert router.cancel()["reason"] == orders.NO_ACCOUNT_REFUSAL
    assert router.flatten(5000.0, 1)["ok"] is False
    assert router.status()["positions_open"] == 0 and router.status()["position"]["side"] == "flat"


def test_a_side_that_is_not_a_side_is_refused_with_its_own_gate():
    router = OrderRouter(account())
    result = router.route("sideways", 1)
    assert result["ok"] is False and result["gate"] == "side"
    assert result["reason"] == "an order needs a side — 'buy' or 'sell'"
    assert result["driver"] == "paper" and result["order"] is None


# ══════════════════════════════════════════════════════════════
# The live path refuses, twice over
# ══════════════════════════════════════════════════════════════

def test_the_bridge_refuses_with_the_switch_on_and_with_it_off():
    off = OrderRouter(account(), settings={"driver": "bridge"})
    blocked = off.route("buy", 1)
    assert blocked["ok"] is False and blocked["gate"] == "live_disabled"
    assert blocked["reason"] == orders.LIVE_REFUSAL and blocked["order"] is None
    assert blocked["route"] is None and blocked["driver"] == "bridge"
    assert blocked["gates"] == off.gates("buy", 1)                  # the table travels with the refusal

    # Even with the switch cleared there is no counterparty in this build, so the second lock holds
    # and the driver itself refuses: an order can never reach a live account by accident.
    account_ = account()
    on = OrderRouter(account_, settings={"driver": "bridge", "live_disabled": False})
    refused = on.route("buy", 1, template="scalp")
    assert refused["ok"] is False and refused["gate"] == "live_account"
    assert refused["reason"] == orders.BRIDGE_REFUSAL and refused["order"] is None
    # §148 T1-D12: the old line read `on.account is None or isinstance(...)` — the first disjunct was
    # dead for this fixture (the router is built WITH an account), so it tested nothing. What the
    # bridge actually owes is narrower and checkable: it is never handed an account to reach.
    assert isinstance(on.driver(), BridgeDriver) and not hasattr(on.driver(), "account")
    assert on.account is account_                       # the paper account rides along untouched
    assert on.cancel()["ok"] is False and on.cancel()["reason"] == orders.BRIDGE_REFUSAL
    assert on.flatten(5000.0, 1)["ok"] is False and on.flatten(5000.0, 1)["fills"] == []
    assert isinstance(on.driver(), BridgeDriver) and on.driver().submit("buy", 1)["ok"] is False


def test_no_market_print_can_produce_a_live_fill():
    """The tape's own door: the bridge driver has no on_trade at all, so nothing can fill on it."""
    driver = BridgeDriver()
    assert not hasattr(driver, "on_trade")
    assert not [name for name, _ in inspect.getmembers(driver, inspect.ismethod)
                if name in ("on_trade", "apply", "fill")]


def test_the_default_settings_never_route_to_the_bridge():
    router = OrderRouter(account())
    assert router.settings["driver"] == "paper" and router.settings["live_disabled"] is True
    assert isinstance(router.driver(), PaperDriver)
    assert router.route("buy", 1)["route"] == "/api/atlas/replay/paper/order"


# ══════════════════════════════════════════════════════════════
# The door: what actually arrives at the account
# ══════════════════════════════════════════════════════════════

def test_a_routed_order_arrives_with_its_template_and_arms_the_bracket():
    account_ = account()
    router = OrderRouter(account_)
    receipt = router.route("buy", 2, kind="market", template="runner")
    assert receipt["ok"] is True and receipt["driver"] == "paper"
    assert receipt["route"] == "/api/atlas/replay/paper/order"
    assert receipt["gate"] == "" and receipt["reason"] == ""
    order = receipt["order"]
    assert order["plan_template"]["id"] == "runner" and order["side"] == "buy"
    assert receipt["body"] == {"side": "buy", "size": 2.0, "kind": "market", "price": None,
                               "template": "runner"}

    fills = account_.on_trade(5000.0, 2, "sell", 2_000)
    assert [f["reason"] for f in fills] == ["market"]                # the tape still owns the fill
    plan = account_.plan()
    assert plan["status"] == "live" and plan["stop_loss"] == 4998.0 and plan["take_profit"] == 5008.0
    assert account_.exits() == {"stop_loss": 4998.0, "take_profit": 5008.0}
    assert [o["plan_leg"] for o in account_.open_orders()] == ["partial"]


def test_a_routed_order_carries_the_typed_levels_it_was_given():
    account_ = account()
    router = OrderRouter(account_)
    receipt = router.route("sell", 1, kind="limit", price=5002.0, stop_loss=5004.0, take_profit=4998.0)
    assert receipt["ok"] is True and receipt["order"]["kind"] == "limit"
    assert receipt["body"] == {"side": "sell", "size": 1.0, "kind": "limit", "price": 5002.0,
                               "stop_loss": 5004.0, "take_profit": 4998.0}
    assert account_.on_trade(5002.0, 1, "buy", 1_000)[0]["reason"] == "limit"
    assert account_.exits() == {"stop_loss": 5004.0, "take_profit": 4998.0}


def test_the_accounts_own_refusal_travels_back_through_the_receipt():
    account_ = account()
    account_.on_trade(2450.0, 1, "buy", 900)                        # a tape far from the order
    router = OrderRouter(account_)
    receipt = router.route("sell", 1, kind="limit", price=1.0)
    assert receipt["ok"] is False and receipt["gate"] == "account"
    assert "would fill the moment it is placed" in receipt["reason"]
    assert receipt["order"]["status"] == "rejected"


def test_cancel_reaches_the_driver_and_says_what_it_did():
    account_ = account()
    router = OrderRouter(account_)
    router.route("buy", 1, kind="limit", price=4990.0)
    router.route("sell", 1, kind="limit", price=5050.0)
    assert [o["id"] for o in account_.open_orders()] == ["o1", "o2"]

    one = router.cancel("o1")
    assert one == {"ok": True, "driver": "paper", "route": "/api/atlas/replay/paper/cancel",
                   "reason": "", "cancelled": ["o1"]}
    missing = router.cancel("o9")
    assert missing["ok"] is False and "not working" in missing["reason"]
    every = router.cancel()
    assert every["ok"] is True and every["cancelled"] == ["o2"] and account_.open_orders() == []


def test_the_router_status_is_the_panels_read_out():
    account_ = account()
    router = OrderRouter(account_, settings={"max_size": 4})
    filled(account_, "buy", 1, 5000.0, ts_ms=1_000)
    status = router.status()
    assert status["ok"] is True and status["driver"] == "paper" and status["live_disabled"] is True
    assert status["routes"] == orders.ROUTES["paper"]
    assert status["settings"]["max_size"] == 4.0
    assert status["positions_open"] == 1 and status["position"]["side"] == "long"
    assert status["day"] == "" and status["day_ticks"] == 0.0
    assert [v["gate"] for v in status["gates"]] == ["driver", "size", "max_size", "daily_loss_cap",
                                                    "max_positions"]
    assert status["refusals"] == {"live": orders.LIVE_REFUSAL, "bridge": orders.BRIDGE_REFUSAL,
                                  "account": orders.NO_ACCOUNT_REFUSAL}
    json.dumps(status)


def test_set_account_moves_the_router_onto_a_new_session():
    first, second = account(), account()
    router = OrderRouter(first)
    assert router.account is first
    router.set_account(second)
    assert router.account is second and first not in router._accounts
    router.attach(first)
    assert router.account is second and router.open_positions() == 0
    assert router.set_account(None) is None and router.account is None


# ══════════════════════════════════════════════════════════════
# The app's routes
# ══════════════════════════════════════════════════════════════

@pytest.fixture()
def client(monkeypatch):
    """The order router's own routes, mounted alone — no launcher, no session, no config file."""
    monkeypatch.setattr(orders, "_SESSION", {"router": None})
    monkeypatch.setattr(orders, "_stored", lambda key: None)
    app = FastAPI()
    app.include_router(orders.router)
    return TestClient(app)


def test_every_trading_route_refuses_politely_with_no_session(client):
    status = client.get("/api/control/trading/status").json()
    assert status["ok"] is True and status["bound"] is False
    assert status["settings"] == orders.DEFAULTS and status["live_disabled"] is True
    assert status["routes"] == orders.ROUTES["paper"]

    routed = client.post("/api/control/trading/route", json={"side": "buy", "size": 1}).json()
    assert routed["ok"] is False and routed["reason"] == orders.NO_SESSION_REFUSAL
    assert routed["order"] is None and routed["bound"] is False

    cancelled = client.post("/api/control/trading/cancel", json={}).json()
    assert cancelled["ok"] is False and cancelled["reason"] == orders.NO_SESSION_REFUSAL


def test_the_templates_route_answers_the_stored_block_or_the_shipped_one(client):
    body = client.get("/api/control/trading/templates").json()
    assert body["ok"] is True and body["atm"] == atm.DEFAULTS
    assert [t["id"] for t in body["atm"]["templates"]] == ["scalp", "intraday", "runner"]


def test_a_bound_session_routes_through_the_apps_own_door(client):
    account_ = account()
    orders.bind_account(account_, settings={"max_size": 5})
    status = client.get("/api/control/trading/status").json()
    assert status["bound"] is True and status["driver"] == "paper"
    assert status["settings"]["max_size"] == 5.0

    routed = client.post("/api/control/trading/route",
                         json={"side": "buy", "size": 2, "kind": "market", "template": "intraday"}).json()
    assert routed["ok"] is True and routed["error"] == ""
    assert routed["order"]["plan_template"]["id"] == "intraday"
    assert routed["state"]["position"]["side"] == "flat"             # no print yet: no fill

    account_.on_trade(5000.0, 2, "sell", 2_000)
    state = client.get("/api/control/trading/status").json()
    assert state["position"]["side"] == "long" and state["positions_open"] == 1
    assert [v["gate"] for v in state["gates"]] == ["driver", "size", "max_size", "daily_loss_cap",
                                                   "max_positions"]

    blocked = client.post("/api/control/trading/route", json={"side": "buy", "size": 9}).json()
    assert blocked["ok"] is False and blocked["gate"] == "max_size"
    assert blocked["error"] == "order refused: size 9 is past the max size 5 in Risk settings"

    cancelled = client.post("/api/control/trading/cancel", json={}).json()
    assert cancelled["ok"] is True and cancelled["cancelled"] == ["o2"]     # the plan's partial
    # binding a second session keeps the same router object, now on the new account
    other = account()
    router = orders.bind_account(other)
    assert router is orders.session_router() and router.account is other


def test_the_session_router_is_only_ever_what_bind_account_made(monkeypatch):
    monkeypatch.setattr(orders, "_SESSION", {"router": "not a router"})
    assert orders.session_router() is None
    monkeypatch.setattr(orders, "_SESSION", {})
    assert orders.session_router() is None
    router = orders.session_router()
    assert router is None
    monkeypatch.setattr(orders, "_SESSION", {"router": OrderRouter(account())})
    assert isinstance(orders.session_router(), OrderRouter)
