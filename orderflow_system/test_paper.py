"""paper: the fills, the arithmetic and the journal rows of the Replay view's paper account.

The account is a pure state machine, so every rule it claims can be pinned here without a tape, a
socket or a clock:

  * a market order fills at the next print, a limit at or through its own price (at that price), a
    stop at its trigger — and the prints drive everything, nothing else does
  * stop-loss and take-profit are checked against every print, and a single print inside both
    resolves to the stop, deterministically
  * PnL is in ticks, the journal's unit: (exit − entry) / tick_size × direction × size
  * a same-size opposite fill nets flat; an oversized one reduces first and flips the remainder
  * every closed leg is a ``trade_journal`` row, and a session round-trips through JSON

The default test instrument is a 0.25-tick future, so the tick arithmetic in the expected numbers
is exact rather than approximate.
"""

from __future__ import annotations

import json

import pytest

from orderflow_system.data.models import Side
from orderflow_system.desktop import paper
from orderflow_system.desktop.paper import PaperAccount

SYMBOL = "ESZ6"
TICK = 0.25
BALANCE = 100_000.0
BALANCE_TICKS = BALANCE / TICK        # 400_000 ticks — the funded balance in journal units


def make(**kwargs) -> PaperAccount:
    """The default instrument: a 0.25-tick index future with a 100k bankroll."""
    return PaperAccount(symbol=SYMBOL, tick_size=TICK, starting_balance=BALANCE, **kwargs)


def fill(account: PaperAccount, side: str, size: float, price: float, *,
         ts_ms: int = 1_000, **submit_kwargs) -> dict:
    """Submit a market order and drive the one print that fills it — the next print."""
    account.submit(side, size, ts_ms=ts_ms - 1, **submit_kwargs)
    fills = account.on_trade(price, size, "sell" if side == "buy" else "buy", ts_ms)
    assert len(fills) == 1, fills
    return fills[0]


# ══════════════════════════════════════════════════════════════
# The tape fills orders; nothing else does
# ══════════════════════════════════════════════════════════════

def test_a_market_order_fills_at_the_next_print():
    account = make()
    assert account.on_trade(4999.5, 5, "buy", ts_ms=900) == []      # a print before the order exists

    order = account.submit("buy", 2, ts_ms=1_000)
    assert order["id"] == "o1" and order["status"] == "working"
    assert order["filled_ms"] is None and order["fill_price"] is None and order["reason"] == ""
    assert account.position()["side"] == "flat"                      # nothing has printed yet

    fills = account.on_trade(5000.25, 7, "sell", ts_ms=1_200)
    assert fills == [{"order_id": "o1", "side": "buy", "size": 2.0, "price": 5000.25,
                      "ts_ms": 1_200, "kind": "market", "reason": "market"}]
    assert account.position() == {"side": "long", "size": 2.0,
                                  "entry_price": 5000.25, "entry_ms": 1_200}
    assert account.open_orders() == []
    # the row the caller was handed is the account's own, so it shows the fill
    assert order["status"] == "filled" and order["fill_price"] == 5000.25 and order["filled_ms"] == 1_200
    # and a filled order does not fill again on the prints that follow
    assert account.on_trade(5001.0, 3, "buy", ts_ms=1_300) == []


def test_a_limit_waits_for_its_price_and_fills_at_its_own_price():
    account = make()
    order = account.submit("buy", 1, kind="limit", price=4999.0, ts_ms=10)
    assert order["status"] == "working" and order["kind"] == "limit" and order["price"] == 4999.0
    assert [o["id"] for o in account.open_orders()] == ["o1"]

    # approached from above, never reached: no fill, and the order stays on the book
    assert account.on_trade(4999.25, 4, "sell", ts_ms=20) == []
    assert account.on_trade(5000.0, 2, "buy", ts_ms=30) == []
    assert [o["id"] for o in account.open_orders()] == ["o1"]

    # traded through: fills at the limit, not at the print — and only once
    fills = account.on_trade(4998.5, 4, "sell", ts_ms=40)
    assert fills == [{"order_id": "o1", "side": "buy", "size": 1.0, "price": 4999.0,
                      "ts_ms": 40, "kind": "limit", "reason": "limit"}]
    assert account.position() == {"side": "long", "size": 1.0, "entry_price": 4999.0, "entry_ms": 40}
    assert account.on_trade(4990.0, 1, "sell", ts_ms=50) == []


def test_a_sell_limit_waits_for_its_price():
    account = make()
    account.submit("sell", 1, kind="limit", price=5001.0, ts_ms=10)
    assert account.on_trade(5000.75, 3, "buy", ts_ms=20) == []       # approached from below
    fills = account.on_trade(5001.0, 3, "buy", ts_ms=30)
    assert fills[0]["kind"] == "limit" and fills[0]["price"] == 5001.0
    assert account.position() == {"side": "short", "size": 1.0, "entry_price": 5001.0, "entry_ms": 30}


def test_a_buy_stop_triggers_upward():
    account = make()
    account.submit("buy", 2, kind="stop", price=5001.0, ts_ms=10)
    assert account.on_trade(5000.75, 2, "buy", ts_ms=20) == []       # still below the trigger
    fills = account.on_trade(5001.0, 2, "buy", ts_ms=30)
    assert fills == [{"order_id": "o1", "side": "buy", "size": 2.0, "price": 5001.0,
                      "ts_ms": 30, "kind": "stop", "reason": "stop"}]
    assert account.position() == {"side": "long", "size": 2.0, "entry_price": 5001.0, "entry_ms": 30}


def test_a_sell_stop_triggers_downward():
    account = make()
    account.submit("sell", 1, kind="stop", price=4999.0, ts_ms=10)
    assert account.on_trade(4999.25, 2, "sell", ts_ms=20) == []      # still above the trigger
    fills = account.on_trade(4998.75, 2, "sell", ts_ms=30)
    assert fills[0]["kind"] == "stop" and fills[0]["price"] == 4999.0
    assert account.position() == {"side": "short", "size": 1.0, "entry_price": 4999.0, "entry_ms": 30}

def test_an_order_the_market_has_already_passed_is_refused_not_filled_at_a_fantasy_price():
    # Measured live 2026-09-18: a sell limit at 1.0 on a ~2,450 tape stayed "working", then filled
    # at 1.0 — a price that never traded — booking a 244,699-tick loss into the journal.
    account = make()
    account.on_trade(2450.0, 2, "buy", ts_ms=900)

    refused = account.submit("sell", 1, kind="limit", price=1.0, ts_ms=1_000)
    assert refused["status"] == "rejected"
    assert refused["reason"] == ("a sell limit at 1 would fill the moment it is placed — at a "
                                 "price the tape never traded (last 2450)")
    assert account.open_orders() == []
    assert account.on_trade(2449.5, 1, "sell", ts_ms=1_100) == []   # a refused order never fills
    assert account.closed_trades() == []

    # The mirror cases are refused too: a buy limit above the market (marketable at submit), a buy
    # stop whose trigger the tape already passed, a sell stop already triggered on the way up.
    assert account.submit("buy", 1, kind="limit", price=2451.0, ts_ms=1_200)["status"] == "rejected"
    assert account.submit("buy", 1, kind="stop", price=2400.0, ts_ms=1_300)["status"] == "rejected"
    assert account.submit("sell", 1, kind="stop", price=2500.0, ts_ms=1_400)["status"] == "rejected"
    # ...and the same orders on the resting side still rest, untouched.
    assert account.submit("sell", 1, kind="limit", price=2451.0, ts_ms=1_500)["status"] == "working"
    assert account.submit("buy", 1, kind="limit", price=2449.0, ts_ms=1_600)["status"] == "working"
    assert account.submit("buy", 1, kind="stop", price=2451.0, ts_ms=1_700)["status"] == "working"
    assert account.submit("sell", 1, kind="stop", price=2449.0, ts_ms=1_800)["status"] == "working"


def test_a_gapped_stop_fills_at_its_trigger_not_at_the_print():
    account = make()
    account.submit("buy", 1, kind="stop", price=5001.0, ts_ms=10)
    fills = account.on_trade(5003.0, 9, "buy", ts_ms=20)             # the tape jumped the trigger
    assert fills[0]["price"] == 5001.0                               # no slippage is modelled


def test_a_print_without_a_usable_price_is_ignored():
    account = make()
    account.submit("buy", 1, ts_ms=1)
    assert account.on_trade(None, 1, "buy", ts_ms=2) == []
    assert account.on_trade(float("nan"), 1, "buy", ts_ms=2) == []
    assert account.on_trade("nonsense", 1, "buy", ts_ms=2) == []
    assert account.flatten(None, 3) == []
    assert account.submit("buy", 1, ts_ms=4)["status"] == "working"   # the order is still waiting
    assert account.on_trade(5000.0, 1, "buy", ts_ms=5) != []


# ══════════════════════════════════════════════════════════════
# Exits: stop-loss, take-profit, flatten
# ══════════════════════════════════════════════════════════════

def test_a_stop_loss_closes_a_long_at_its_stop():
    account = make()
    fill(account, "buy", 1, 5000.0, ts_ms=1_000, stop_loss=4999.0, take_profit=5004.0)
    fills = account.on_trade(4998.75, 5, "sell", ts_ms=2_000)        # through the stop
    assert fills == [{"order_id": None, "side": "sell", "size": 1.0, "price": 4999.0,
                      "ts_ms": 2_000, "kind": "stop_loss", "reason": "stop_loss"}]
    assert account.position()["side"] == "flat" and account.open_orders() == []
    row = account.closed_trades()[0]
    assert row["exit_price"] == 4999.0 and row["pnl_ticks"] == -4.0
    assert account.on_trade(4990.0, 1, "sell", ts_ms=3_000) == []    # the stop is one-shot


def test_a_take_profit_closes_a_long_at_its_target():
    account = make()
    fill(account, "buy", 1, 5000.0, ts_ms=1_000, stop_loss=4998.0, take_profit=5002.0)
    fills = account.on_trade(5002.25, 5, "buy", ts_ms=2_000)
    assert fills[0]["kind"] == "take_profit" and fills[0]["reason"] == "take_profit"
    assert fills[0]["price"] == 5002.0
    assert account.closed_trades()[0]["pnl_ticks"] == 8.0


def test_a_short_stops_up_and_targets_down():
    stopped = make()
    fill(stopped, "sell", 2, 5002.0, ts_ms=1_000, stop_loss=5004.0, take_profit=4998.0)
    assert stopped.on_trade(5003.0, 1, "buy", ts_ms=1_500) == []     # between the levels: nothing
    fills = stopped.on_trade(5004.0, 1, "buy", ts_ms=2_000)
    assert fills[0]["reason"] == "stop_loss" and fills[0]["price"] == 5004.0
    assert stopped.closed_trades()[0]["direction"] == "short"
    assert stopped.closed_trades()[0]["pnl_ticks"] == -16.0          # 8 ticks × 2, against

    targeted = make()
    fill(targeted, "sell", 2, 5002.0, ts_ms=1_000, stop_loss=5004.0, take_profit=4998.0)
    fills = targeted.on_trade(4997.5, 1, "sell", ts_ms=2_000)
    assert fills[0]["reason"] == "take_profit" and fills[0]["price"] == 4998.0
    assert targeted.closed_trades()[0]["pnl_ticks"] == 32.0          # 16 ticks × 2


def test_one_print_inside_both_triggers_takes_the_stop():
    """An inverted pair — the stop and the target round the wrong way — puts one print inside both
    levels. The tape holds a single price and cannot say which side was reached first, so the stop
    is checked first and wins. A fixed rule, never a guess at the path the tape did not record."""
    account = make()
    account.submit("buy", 1, kind="limit", price=5000.0, ts_ms=900,
                   stop_loss=4999.0, take_profit=4997.0)
    fills = account.on_trade(4998.0, 3, "sell", ts_ms=1_000)     # through the limit, inside both
    assert [f["reason"] for f in fills] == ["limit", "stop_loss"]
    assert fills[0]["price"] == 5000.0                           # the limit, at its own price
    assert fills[1]["price"] == 4999.0                           # the stop it was given, not the target
    assert account.closed_trades()[0]["pnl_ticks"] == -4.0

    short = make()
    short.submit("sell", 1, kind="limit", price=5000.0, ts_ms=900,
                 stop_loss=5001.0, take_profit=5002.0)
    fills = short.on_trade(5001.5, 2, "buy", ts_ms=1_000)
    assert [f["reason"] for f in fills] == ["limit", "stop_loss"]
    assert fills[1]["price"] == 5001.0


def test_flatten_closes_the_position_at_the_given_print():
    account = make()
    fill(account, "buy", 2, 5000.0, ts_ms=1_000)
    assert account.flatten(None, 1_500) == []
    assert account.position()["side"] == "long"                      # a bad price is not a close

    fills = account.flatten(5002.0, 2_000)
    assert fills == [{"order_id": None, "side": "sell", "size": 2.0, "price": 5002.0,
                      "ts_ms": 2_000, "kind": "flatten", "reason": "flatten"}]
    assert account.position() == {"side": "flat", "size": 0.0, "entry_price": 0.0, "entry_ms": 0}
    assert account.flatten(5003.0, 3_000) == []                      # nothing left to close
    row = account.closed_trades()[0]
    assert row["exit_price"] == 5002.0 and row["pnl_ticks"] == 16.0


def test_a_mark_is_a_valuation_never_a_fill():
    account = make()
    fill(account, "buy", 1, 5000.0, ts_ms=1_000, stop_loss=4999.0)
    account.mark(4900.0)                                             # far through the stop
    assert account.position()["side"] == "long" and account.closed_trades() == []
    assert account.on_trade(4900.0, 1, "sell", ts_ms=2_000)[0]["reason"] == "stop_loss"


# ══════════════════════════════════════════════════════════════
# Position arithmetic
# ══════════════════════════════════════════════════════════════

def test_pnl_ticks_are_pinned_for_both_directions():
    long_account = make()
    fill(long_account, "buy", 3, 5000.25, ts_ms=1_000)
    fill(long_account, "sell", 3, 5001.75, ts_ms=2_000)
    assert long_account.closed_trades()[0]["pnl_ticks"] == 18.0       # 6 ticks × 3

    short_account = make()
    fill(short_account, "sell", 2, 5002.0, ts_ms=1_000)
    fill(short_account, "buy", 2, 5000.0, ts_ms=2_000)
    assert short_account.closed_trades()[0]["pnl_ticks"] == 16.0      # 8 ticks × 2
    assert short_account.stats()["realised_ticks"] == 16.0


def test_the_same_size_the_other_way_nets_to_flat():
    account = make()
    fill(account, "buy", 2, 5000.0, ts_ms=1_000)
    account.submit("sell", 2, ts_ms=1_900)
    fills = account.on_trade(5001.0, 9, "buy", ts_ms=2_000)
    assert fills[0]["side"] == "sell" and fills[0]["size"] == 2.0
    assert account.position() == {"side": "flat", "size": 0.0, "entry_price": 0.0, "entry_ms": 0}
    assert account.stats()["closed"] == 1 and account.stats()["realised_ticks"] == 8.0


def test_an_oversized_opposite_order_reduces_then_flips():
    account = make()
    fill(account, "buy", 2, 5000.0, ts_ms=1_000)
    account.submit("sell", 5, ts_ms=1_900)
    fills = account.on_trade(5001.0, 30, "sell", ts_ms=2_000)
    assert len(fills) == 1                                           # one order, one fill
    assert account.position() == {"side": "short", "size": 3.0,
                                  "entry_price": 5001.0, "entry_ms": 2_000}
    rows = account.closed_trades()
    assert len(rows) == 1 and rows[0]["direction"] == "long"
    assert rows[0]["entry_price"] == 5000.0 and rows[0]["exit_price"] == 5001.0
    assert rows[0]["pnl_ticks"] == 8.0                               # 4 ticks × 2

    account.submit("buy", 3, ts_ms=2_900)
    account.on_trade(4999.0, 12, "sell", ts_ms=3_000)
    assert account.position()["side"] == "flat"
    assert account.closed_trades()[1]["direction"] == "short"
    assert account.closed_trades()[1]["pnl_ticks"] == 24.0           # 8 ticks × 3
    assert account.stats()["realised_ticks"] == 32.0


def test_a_partial_reduction_keeps_the_entry_and_the_age():
    account = make()
    fill(account, "buy", 4, 5000.0, ts_ms=1_000, stop_loss=4990.0)
    account.submit("sell", 1, ts_ms=1_900)
    account.on_trade(5010.0, 2, "buy", ts_ms=2_000)
    assert account.position() == {"side": "long", "size": 3.0,
                                  "entry_price": 5000.0, "entry_ms": 1_000}
    assert account.closed_trades()[0]["pnl_ticks"] == 40.0           # 40 ticks × 1
    assert account.closed_trades()[0]["stop_loss"] == 4990.0


def test_one_print_fills_markets_then_entries_then_exits():
    account = make()
    fill(account, "buy", 1, 5000.0, ts_ms=1_000, stop_loss=4999.0)
    account.submit("buy", 1, ts_ms=1_100)                            # a market order
    account.submit("buy", 1, kind="limit", price=4997.0, ts_ms=1_200)
    fills = account.on_trade(4997.0, 5, "sell", ts_ms=2_000)
    assert [f["reason"] for f in fills] == ["market", "limit", "stop_loss"]
    assert fills[0]["price"] == 4997.0 and fills[1]["price"] == 4997.0
    assert account.position()["side"] == "flat"                      # the stop took all three
    assert account.closed_trades()[0]["pnl_ticks"] == 12.0           # the stop, at its level


# ══════════════════════════════════════════════════════════════
# The book: refusals, the position cap, cancels
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("order_kwargs", [
    {"side": "sideways", "size": 1},
    {"side": "buy", "size": 0},
    {"side": "buy", "size": -2},
    {"side": "buy", "size": "abc"},
    {"side": "buy", "size": 1, "kind": "trailing"},
    {"side": "buy", "size": 1, "kind": "limit"},
    {"side": "buy", "size": 1, "kind": "limit", "price": 0},
    {"side": "buy", "size": 1, "kind": "stop", "price": -1},
    {"side": "buy", "size": 1, "kind": "stop", "price": None},
])
def test_a_bad_order_is_a_rejection_row_not_an_exception(order_kwargs):
    account = make()
    order = account.submit(**order_kwargs)
    assert order["status"] == "rejected" and order["reason"]
    assert account.open_orders() == [] and account.position()["side"] == "flat"
    assert account.cancel(order["id"]) is False
    stats = account.stats()
    assert stats["orders_rejected"] == 1 and stats["orders_filled"] == 0


def test_order_ids_count_up_and_a_refusal_still_takes_one():
    account = make()
    first = account.submit("buy", 1, ts_ms=1)
    refused = account.submit("buy", 0, ts_ms=2)
    third = account.submit("sell", 1, ts_ms=3)
    assert (first["id"], refused["id"], third["id"]) == ("o1", "o2", "o3")


def test_sides_and_kinds_are_case_insensitive_and_take_the_app_enum():
    account = make()
    order = account.submit("BUY", 1, kind="LIMIT", price=4999.0, ts_ms=1)
    assert order["side"] == "buy" and order["kind"] == "limit"
    assert account.on_trade(4999.0, 1, "Sell", ts_ms=2)[0]["side"] == "buy"

    enum_account = make()
    assert enum_account.submit(Side.BUY, 1, ts_ms=1)["side"] == "buy"
    fills = enum_account.on_trade(5000.0, 1, Side.SELL, ts_ms=2)
    assert fills[0]["reason"] == "market" and fills[0]["side"] == "buy"


def test_max_position_refuses_what_would_exceed_it_and_allows_what_reduces():
    account = make(max_position=5)
    refusal = account.submit("buy", 6, ts_ms=1)
    assert refusal["status"] == "rejected" and "max_position" in refusal["reason"]
    assert account.position()["side"] == "flat" and account.open_orders() == []

    fill(account, "buy", 5, 5000.0, ts_ms=1_000)
    assert account.submit("buy", 1, ts_ms=1_100)["status"] == "rejected"      # 5 + 1 > 5
    assert account.submit("sell", 1, ts_ms=1_200)["status"] == "working"      # reducing is fine
    assert account.submit("sell", 5, ts_ms=1_300)["status"] == "working"      # netting flat is fine
    assert account.submit("sell", 11, ts_ms=1_400)["status"] == "rejected"    # −6 is past −5
    assert account.stats()["orders_rejected"] == 3


def test_cancel_takes_a_working_order_off_the_book():
    account = make()
    order = account.submit("buy", 1, kind="limit", price=4999.0, ts_ms=5)
    assert account.cancel(order["id"]) is True
    assert order["status"] == "cancelled" and order["reason"]
    assert account.open_orders() == []
    assert account.on_trade(4999.0, 1, "sell", ts_ms=6) == []        # a cancelled order cannot fill
    assert account.cancel(order["id"]) is False                      # already off the book
    assert account.cancel("o99") is False                            # never existed

    filled = fill(account, "buy", 1, 5000.0, ts_ms=7_000)
    assert account.cancel(filled["order_id"]) is False               # filled orders are not working


# ══════════════════════════════════════════════════════════════
# The numbers the journal and the UI read
# ══════════════════════════════════════════════════════════════

def test_the_mark_moves_with_the_price():
    account = make()
    fill(account, "buy", 2, 5000.0, ts_ms=1_000)
    assert account.mark(5000.0) == {"unrealised_ticks": 0.0,
                                    "equity_ticks": BALANCE_TICKS,
                                    "balance_ticks": BALANCE_TICKS}
    up = account.mark(5001.0)
    assert up["unrealised_ticks"] == 8.0                             # 4 ticks × 2
    assert up["balance_ticks"] == BALANCE_TICKS                      # banked money does not move
    assert up["equity_ticks"] == BALANCE_TICKS + 8.0
    down = account.mark(4999.5)
    assert down["unrealised_ticks"] == -4.0                          # 2 ticks × 2, against
    assert down["equity_ticks"] == BALANCE_TICKS - 4.0


def test_stats_tell_the_session_in_numbers():
    account = make()
    fill(account, "buy", 2, 5000.0, ts_ms=1_000, stop_loss=4999.0, take_profit=5002.0)
    account.submit("buy", 1, kind="limit", price=4000.0, ts_ms=1_500)         # still resting
    account.submit("buy", 0, ts_ms=1_600)                                     # refused
    fill(account, "sell", 1, 5001.0, ts_ms=2_000)                             # half off, +4 ticks
    account.on_trade(5002.0, 1, "buy", ts_ms=2_500)                           # target, +8 ticks

    assert account.stats() == {
        "orders_submitted": 4,
        "orders_filled": 2,
        "orders_rejected": 1,
        "closed": 2,
        "wins": 2,
        "losses": 0,
        "realised_ticks": 12.0,
        "unrealised_ticks": 0.0,
        "equity_ticks": BALANCE_TICKS + 12.0,
    }
    assert len(account.open_orders()) == 1                            # the resting limit is still there


def test_a_closed_trade_is_a_journal_row():
    account = make()
    fill(account, "buy", 2, 5000.0, ts_ms=1_000, stop_loss=4998.0, take_profit=5004.0)
    fills = account.on_trade(5004.0, 2, "sell", ts_ms=2_000)          # the target takes it
    assert fills[0]["reason"] == "take_profit"

    rows = account.closed_trades()
    assert len(rows) == 1
    row = rows[0]
    assert tuple(row) == paper.JOURNAL_COLUMNS
    assert row == {
        "instrument": SYMBOL,
        "direction": "long",
        "entry_time_ms": 1_000,
        "exit_time_ms": 2_000,
        "entry_price": 5000.0,
        "exit_price": 5004.0,
        "stop_loss": 4998.0,
        "take_profit": 5004.0,
        "pnl_ticks": 32.0,
        "rr_ratio": 2.0,
    }
    json.dumps(row)                                                   # journal-ready as it stands


def test_a_position_without_exits_journals_zero_levels():
    account = make()
    fill(account, "sell", 1, 5000.0, ts_ms=1_000)
    fill(account, "buy", 1, 4999.0, ts_ms=2_000)
    row = account.closed_trades()[0]
    assert row["direction"] == "short"
    assert (row["stop_loss"], row["take_profit"], row["rr_ratio"]) == (0.0, 0.0, 0.0)


def test_the_rows_go_straight_into_the_trade_journal():
    """The point of the row shape: a session's closed legs drop into the journal's own reader."""
    journal = pytest.importorskip("orderflow_system.desktop.journal")
    account = make()
    fill(account, "buy", 2, 5000.0, ts_ms=1_000, stop_loss=4998.0, take_profit=5004.0)
    account.on_trade(5004.0, 2, "sell", ts_ms=2_000)

    traded = journal.normalise_trades(account.closed_trades())
    assert [row["instrument"] for row in traded] == [SYMBOL]
    assert [row["direction"] for row in traded] == ["LONG"]        # the journal's own casing
    assert journal.stats(traded)["total_pnl"] == 32.0


# ══════════════════════════════════════════════════════════════
# A session survives being stored
# ══════════════════════════════════════════════════════════════

def test_to_dict_round_trips_through_json():
    account = make(max_position=5)
    fill(account, "buy", 2, 5000.0, ts_ms=1_000, stop_loss=4999.0, take_profit=5002.0)
    account.submit("buy", 1, kind="limit", price=4995.0, ts_ms=1_100)          # left working
    account.submit("buy", 99, ts_ms=1_200)                                     # refused
    account.on_trade(5002.0, 4, "sell", ts_ms=2_000)                           # target takes it
    assert account.position()["side"] == "flat"

    snapshot = json.loads(json.dumps(account.to_dict()))
    restored = PaperAccount.from_dict(snapshot)

    assert restored.to_dict() == snapshot
    assert restored.position() == account.position()
    assert restored.open_orders() == account.open_orders()
    assert restored.closed_trades() == account.closed_trades()
    assert restored.stats() == account.stats()
    assert restored.symbol == SYMBOL and restored.tick_size == TICK
    assert restored.max_position == 5.0

    order = restored.submit("sell", 1, ts_ms=3_000)                            # ids carry on
    assert order["id"] == "o4"
    fills = restored.on_trade(4999.0, 1, "sell", ts_ms=3_100)
    assert fills[0]["price"] == 4999.0
    assert account.on_trade(4999.0, 1, "sell", ts_ms=3_100) == []              # two separate accounts
    assert [o["id"] for o in account.open_orders()] == ["o2"]


# ══════════════════════════════════════════════════════════════
# The bracket, edited after entry (§118)
# ══════════════════════════════════════════════════════════════

def test_exits_can_be_set_moved_and_cleared_on_an_open_position():
    account = make()
    assert account.exits() == {"stop_loss": None, "take_profit": None}
    refused = account.set_exits(stop_loss=4999.0)
    assert refused["ok"] is False and "no open position" in refused["reason"]

    fill(account, "buy", 2, 5000.0, ts_ms=1_000, stop_loss=4999.0, take_profit=5004.0)
    assert account.exits() == {"stop_loss": 4999.0, "take_profit": 5004.0}

    moved = account.set_exits(stop_loss=4999.5, take_profit=5004.0, ts_ms=1_100)
    assert moved["ok"] is True and moved["changed"] is True
    assert account.exits()["stop_loss"] == 4999.5
    # the tape still decides, and the MOVED stop is the one that fires
    fills = account.on_trade(4999.5, 1, "sell", ts_ms=2_000)
    assert fills[0]["reason"] == "stop_loss" and fills[0]["price"] == 4999.5


def test_clearing_one_leg_keeps_the_other_and_junk_is_refused_without_clearing():
    account = make()
    fill(account, "buy", 1, 5000.0, ts_ms=1_000, stop_loss=4999.0, take_profit=5004.0)

    junk = account.set_exits(stop_loss="abc", take_profit=5004.0)
    assert junk["ok"] is False and "stop_loss" in junk["reason"]
    assert account.exits() == {"stop_loss": 4999.0, "take_profit": 5004.0}   # nothing moved

    cleared = account.set_exits(stop_loss=4999.0, take_profit=None)
    assert cleared["ok"] is True and cleared["changed"] is True
    assert account.exits() == {"stop_loss": 4999.0, "take_profit": None}
    assert account.on_trade(5009.0, 1, "buy", ts_ms=2_000) == []             # no target to hit
    assert account.position()["side"] == "long"
    assert account.on_trade(4999.0, 1, "sell", ts_ms=3_000)[0]["reason"] == "stop_loss"


def test_an_unchanged_bracket_reports_changed_false_and_exits_survive_a_round_trip():
    account = make()
    fill(account, "buy", 1, 5000.0, ts_ms=1_000, stop_loss=4999.0)
    same = account.set_exits(stop_loss=4999.0, take_profit=None)
    assert same["ok"] is True and same["changed"] is False
    account.set_exits(stop_loss=4998.0, take_profit=5002.0)
    restored = PaperAccount.from_dict(json.loads(json.dumps(account.to_dict())))
    assert restored.exits() == {"stop_loss": 4998.0, "take_profit": 5002.0}


def test_from_dict_is_tolerant_of_junk():
    account = PaperAccount.from_dict({"tick_size": "abc", "orders": ["nonsense"], "position": None})
    assert account.tick_size == 0.01 and account.open_orders() == []
    assert account.position()["side"] == "flat"
    assert PaperAccount.from_dict({}).to_dict() == PaperAccount(starting_balance=0.0).to_dict()
