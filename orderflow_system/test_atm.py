"""atm: order templates and the bracket they build — pure arithmetic, pinned without a tape.

The module is the plan half of the execution upgrade: a template names a size and a set of tick
distances, and ``plan`` turns an entry price into the legs a position will carry. Everything here
is checkable on a 0.25-tick future, so the expected numbers are exact rather than approximate:

  * a template is coerced, never trusted — junk fields default, distances clamp, ids sanitise
  * ``plan`` rounds every level onto the tick grid and signs every distance with the position
  * ``advance`` is one print's worth of management: break-even, the trailing stop's ratchet, the clock
  * OCO membership is a table, and the sibling cancels are read straight off it
  * every refusal is a sentence, and nothing in the module raises
"""

from __future__ import annotations

import json

import pytest

from orderflow_system.desktop import atm

TICK = 0.25
ENTRY = 5000.0


def runner() -> dict:
    """The shipped template that uses every feature, so one plan exercises one of each."""
    t = atm.template_of(atm.DEFAULTS, "runner")
    assert t is not None
    return t


def make_plan(side: str = "buy", size: float = 2, entry: float = ENTRY,
              template: dict | None = None, **kwargs) -> dict:
    return atm.plan(side, size, entry, template if template is not None else runner(),
                    tick_size=TICK, group="oc1", **kwargs)


# ══════════════════════════════════════════════════════════════
# Templates: coercion, clamping, the shipped set
# ══════════════════════════════════════════════════════════════

def test_the_shipped_templates_are_named_and_complete():
    ids = [t["id"] for t in atm.DEFAULTS["templates"]]
    assert ids == ["scalp", "intraday", "runner"]
    for template in atm.DEFAULTS["templates"]:
        assert tuple(template) == atm.TEMPLATE_FIELDS, template["id"]
        assert template["name"] and template["size"] > 0
        assert template["stop_ticks"] > 0 and template["target_ticks"] > 0


def test_clean_template_coerces_and_clamps_every_field():
    cleaned = atm.clean_template({
        "id": "My Plan!", "name": "  Mine  ", "size": "3", "stop_ticks": "4.6", "target_ticks": -2,
        "breakeven_ticks": None, "trail_ticks": "12", "trail_step_ticks": 0, "time_stop_min": 99_999,
        "partial_ticks": 4, "partial_pct": 150, "unknown": "dropped",
    })
    assert tuple(cleaned) == atm.TEMPLATE_FIELDS                    # unknown keys are dropped
    assert cleaned["id"] == "myplan" and cleaned["name"] == "Mine"
    assert cleaned["size"] == 3.0
    assert cleaned["stop_ticks"] == 5                               # 4.6 rounds to 5 ticks
    assert cleaned["target_ticks"] == 0                             # negative becomes "none"
    assert cleaned["trail_ticks"] == 12 and cleaned["trail_step_ticks"] == 1   # a step of at least 1
    assert cleaned["time_stop_min"] == 24 * 60                      # a day is the ceiling
    assert cleaned["partial_pct"] == 99                             # 150% clamps to 99


#: What every junk input cleans to, measured rather than asserted by construction (§148 T1-D12).
#: The old pair of lines was entailed by ``clean_template``'s own clamps (``max(0, …)``, a default
#: of 1.0): they could not fail and protected nothing. These values can — every one of them moves
#: if a default, a clamp or a key changes.
JUNK_CLEANED = {"id": "", "name": "", "size": 1.0, "stop_ticks": 0, "target_ticks": 0,
                "breakeven_ticks": 0, "trail_ticks": 0, "trail_step_ticks": 1, "time_stop_min": 0,
                "partial_ticks": 0, "partial_pct": 0}


@pytest.mark.parametrize("junk", [None, "nonsense", 42, []])
def test_clean_template_never_raises_on_junk(junk):
    assert atm.clean_template(junk) == JUNK_CLEANED


def test_clean_template_turns_a_non_scalar_id_into_a_name():
    """Pinned as measured (§148 T1-D12): a dict id is string-coerced and mangled, so the template
    arrives named after its own keys rather than id-less. Odd, harmless, and now a value a future
    change has to answer for."""
    cleaned = atm.clean_template({"id": {"nested": 1}, "size": "abc"})
    assert tuple(cleaned) == atm.TEMPLATE_FIELDS
    assert (cleaned["id"], cleaned["name"], cleaned["size"]) == ("nested1", "nested1", 1.0)


def test_a_partial_needs_both_a_level_and_a_share():
    assert atm.clean_template({"id": "a", "partial_ticks": 8, "partial_pct": 0})["partial_ticks"] == 0
    assert atm.clean_template({"id": "a", "partial_ticks": 0, "partial_pct": 50})["partial_pct"] == 0
    both = atm.clean_template({"id": "a", "partial_ticks": 8, "partial_pct": 50})
    assert (both["partial_ticks"], both["partial_pct"]) == (8, 50)


def test_clean_keeps_the_shipped_templates_when_the_patch_is_junk():
    assert atm.clean(None) == atm.DEFAULTS
    assert atm.clean({"templates": "nope", "active": 5}) == atm.DEFAULTS

    replaced = atm.clean({"templates": [{"id": "Only", "stop_ticks": 4}], "active": "only"})
    assert [t["id"] for t in replaced["templates"]] == ["only"]
    assert replaced["active"] == "only"
    # an active id that names nothing in the block is dropped: the next click can never point at nothing
    assert atm.clean({"templates": [{"id": "only", "stop_ticks": 4}], "active": "runner"})["active"] == ""
    # id-less templates are not templates: they cannot be selected, so they are not kept
    assert atm.clean({"templates": [{"stop_ticks": 4}]})["templates"] == atm.DEFAULTS["templates"]
    assert atm.clean({"templates": [{"id": f"t{i}"} for i in range(40)]})["templates"][-1]["id"] == "t11"


def test_clean_round_trips_and_stays_json_ready():
    block = atm.clean({"templates": [{"id": "mine", "name": "Mine", "size": 2, "stop_ticks": 4,
                                      "trail_ticks": 2, "time_stop_min": 15}], "active": "mine"})
    assert atm.clean(json.loads(json.dumps(block))) == block
    assert atm.template_of(block, "MINE")["id"] == "mine"
    assert atm.template_of(block, "nope") is None and atm.template_of(None, "mine") is None


def test_describe_says_the_template_in_words():
    assert atm.describe(runner()) == ("Runner — 2 contracts, stop 8t, target 32t, break-even at 8t, "
                                      "trail 10t/2t, time stop 30 min, 50% off at 8t")
    assert atm.describe({"id": "bare", "name": "Bare", "stop_ticks": 4}) == (
        "Bare — 1 contract, stop 4t, no target")


# ══════════════════════════════════════════════════════════════
# The entry → legs arithmetic
# ══════════════════════════════════════════════════════════════

def test_a_long_plan_puts_stop_below_and_target_above():
    p = make_plan()
    assert p["ok"] is True and p["reason"] == ""
    assert p["side"] == "buy" and p["direction"] == 1 and p["size"] == 2.0 and p["entry"] == ENTRY
    assert p["stop_loss"] == 4998.0 and p["take_profit"] == 5008.0      # 8 and 32 ticks of 0.25
    assert p["breakeven_price"] == 5002.0 and p["breakeven_ticks"] == 8
    assert p["trail_ticks"] == 10 and p["trail_step_ticks"] == 2 and p["trail_stop"] is None
    assert p["rr"] == 4.0 and p["tick_size"] == TICK and p["group"] == "oc1"
    assert p["time_stop_at_ms"] is None                                  # no tape stamp, no clock
    assert p["status"] == "live" and p["breakeven_done"] is False and p["partial_done"] is False
    assert p["text"].startswith("Runner — 2 contracts, stop 8t")


def test_a_short_plan_mirrors_every_level():
    p = make_plan(side="sell", entry=5000.0)
    assert p["direction"] == -1
    assert p["stop_loss"] == 5002.0 and p["take_profit"] == 4992.0
    assert p["breakeven_price"] == 4998.0
    assert p["partial"]["price"] == 4998.0                               # favourable is downwards


def test_the_legs_carry_the_signed_distance_and_the_reduce_side():
    p = make_plan(size=4)
    assert [(leg["name"], leg["ticks"], leg["price"]) for leg in p["legs"]] == [
        ("entry", 0, 5000.0), ("partial", 8, 5002.0), ("stop", -8, 4998.0), ("target", 32, 5008.0)]
    assert [leg["side"] for leg in p["legs"]] == ["buy", "sell", "sell", "sell"]
    assert [leg["role"] for leg in p["legs"]] == ["entry", "reduce", "exit", "exit"]
    assert [leg["size"] for leg in p["legs"]] == [4.0, 2.0, 4.0, 4.0]    # half off at 1R
    assert atm.legs(p) == p["legs"] and atm.legs(p)[0] is not p["legs"][0]   # copies, not aliases
    assert atm.legs(None) == []


def test_levels_are_rounded_onto_the_tick_grid():
    p = atm.plan("buy", 1, 5000.13, {"id": "odd", "name": "Odd", "stop_ticks": 3, "target_ticks": 5},
                 tick_size=0.25, group="g")
    assert p["ok"] and p["entry"] == 5000.25                             # 5000.13 snaps to the grid
    assert p["stop_loss"] == 4999.5 and p["take_profit"] == 5001.5
    assert atm.round_to_tick(5000.115, 0.25) == 5000.0
    assert atm.round_to_tick(-1.2, 0.5) == -1.0                          # halves round away from zero
    assert atm.round_to_tick(1.2, -1) is None and atm.round_to_tick("x", TICK) is None


def test_a_partial_needs_a_second_contract_and_never_takes_the_whole_position():
    assert atm.partial_size(1, 50) == 0.0               # a 1-lot has nothing to halve
    assert atm.partial_size(2, 50) == 1.0
    assert atm.partial_size(3, 50) == 1.0               # whole contracts, floored
    assert atm.partial_size(5, 99) == 4.0               # the last contract always stays on
    assert atm.partial_size(4, 0) == 0.0
    assert atm.partial_size("junk", 50) == 0.0

    one = make_plan(size=1)
    assert one["partial"] is None
    assert "partial" not in [leg["name"] for leg in one["legs"]]


def test_a_template_without_a_stop_is_a_plan_that_says_so():
    p = make_plan(template={"id": "tgt", "name": "Target only", "stop_ticks": 0, "target_ticks": 8})
    assert p["ok"] is True and p["stop_loss"] is None and p["take_profit"] == 5002.0
    assert p["rr"] == 0.0                                # the account's own convention for "no stop"
    assert [leg["name"] for leg in p["legs"]] == ["entry", "target"]


def test_a_plan_can_carry_the_tape_stamp_it_was_built_at():
    timed = atm.clean_template({**runner(), "time_stop_min": 30})
    p = make_plan(template=timed, ts_ms=1_000_000)
    assert p["time_stop_at_ms"] == 1_000_000 + 30 * 60_000 and p["opened_ms"] == 1_000_000
    assert atm.time_stop_hit(p["time_stop_at_ms"], 1_000_000) is False
    assert atm.time_stop_hit(p["time_stop_at_ms"], p["time_stop_at_ms"]) is True
    assert atm.time_stop_hit(None, 9_999_999) is False
    assert atm.time_stop_hit(5_000, 0) is False           # no tape time never fires a clock
    assert atm.time_stop_hit("junk", "junk") is False


@pytest.mark.parametrize("args,reason", [
    (("sideways", 1, ENTRY, None), "a plan needs a side — 'buy' or 'sell'"),
    (("buy", 0, ENTRY, None), "a plan needs a size above 0"),
    (("buy", 1, None, None), "a plan needs the entry price it will fill at — that price is not usable"),
    (("buy", 1, -5, None), "a plan needs the entry price it will fill at — that price is not usable"),
    (("buy", 1, ENTRY, {"id": "empty", "name": "Empty"}),
     "that template names no stop, target, trail or clock — there is no plan in it"),
])
def test_a_plan_that_cannot_be_built_comes_back_as_a_sentence(args, reason):
    side, size, entry, template = args
    template = template if template is not None else runner()
    p = atm.plan(side, size, entry, template, tick_size=TICK)
    assert p == {"ok": False, "reason": reason}


def test_nonsense_inputs_never_raise():
    for side in ("", None, 3, object()):
        assert atm.plan(side, 1, ENTRY, runner(), tick_size=TICK)["ok"] is False
    assert atm.plan("buy", "abc", ENTRY, runner(), tick_size=TICK)["reason"].endswith("size above 0")
    assert atm.plan("buy", 1, "abc", runner(), tick_size=TICK)["ok"] is False
    assert atm.plan("buy", 1, ENTRY, runner(), tick_size="abc") == {
        "ok": False, "reason": "a plan needs the instrument's tick size — that one is not usable"}
    assert atm.plan("buy", 1, ENTRY, runner(), tick_size=0)["ok"] is False
    assert atm.side_of("BUY") == "buy" and atm.side_of(3) == ""
    assert atm.direction_of("SELL") == -1 and atm.direction_of(None) == 0


# ══════════════════════════════════════════════════════════════
# OCO: the legs of one bracket are siblings
# ══════════════════════════════════════════════════════════════

def test_the_oco_group_names_every_sibling_of_every_leg():
    p = make_plan()
    group = atm.oco(p)
    assert group["group"] == "oc1"
    assert group["legs"] == ["entry", "partial", "stop", "target"]
    assert group["resting"] == ["partial", "stop", "target"]
    assert group["cancels"]["stop"] == ["partial", "target"]
    assert group["cancels"]["partial"] == ["stop", "target"]
    assert group["cancels"]["target"] == ["partial", "stop"]
    assert atm.siblings(p, "stop") == ["partial", "target"]
    assert atm.siblings(p, "partial") == ["stop", "target"]
    assert atm.siblings(p, "nope") == [] and atm.siblings(None, "stop") == []


def test_finish_names_the_outcome_and_keeps_the_levels_for_the_journal():
    p = make_plan()
    done = atm.finish(p, "stop_loss", ts_ms=9_000)
    assert done["status"] == "done" and done["outcome"] == "stop_loss" and done["closed_ms"] == 9_000
    assert done["stop_loss"] == 4998.0 and done["take_profit"] == 5008.0
    assert p["status"] == "live"                                        # the caller's plan is untouched
    assert atm.finish(p, "invented")["outcome"] == "unknown"
    assert atm.finish(None, "flatten")["status"] == "done"


# ══════════════════════════════════════════════════════════════
# Managing the plan: break-even, the trail, the clock
# ══════════════════════════════════════════════════════════════

def test_break_even_arms_once_the_trade_has_paid_and_never_widens():
    # Intraday carries a break-even trigger and no trail, so the move is the only thing that can
    # move the stop here — the trail has its own test below.
    p = make_plan(template=atm.clean_template(atm.template_of(atm.DEFAULTS, "intraday")))
    quiet = atm.advance(p, price=5001.0, ts_ms=2_000)                     # 4 ticks: not yet
    assert quiet["ok"] and quiet["changed"] is False and quiet["stop_loss"] == 4998.0
    assert quiet["actions"] == [] and quiet["breakeven_done"] is False

    paid = atm.advance(p, price=5001.5, ts_ms=2_000)                      # 6 ticks: the trigger
    assert paid["actions"] == ["arm_breakeven", "move_stop"]
    assert paid["stop_loss"] == 5000.0 and paid["breakeven_done"] is True
    assert paid["peak"] == 5001.5 and paid["ticks"] == 6.0

    armed = {**p, "stop_loss": 5000.0, "breakeven_done": True}
    back = atm.advance(armed, price=4999.0, ts_ms=2_000)                  # a print below entry
    assert back["actions"] == [] and back["stop_loss"] == 5000.0          # the stop never widens
    assert back["ticks"] == -4.0 and back["peak"] == 5000.0


def test_the_trail_hangs_behind_the_best_price_and_only_ratchets():
    p = {**make_plan(), "breakeven_done": True, "stop_loss": 5000.0, "peak": 5002.0}
    moved = atm.advance(p, price=5004.0, ts_ms=3_000)                     # peak 5004 − 10 ticks
    assert moved["actions"] == ["trail"] and moved["stop_loss"] == 5001.5
    assert moved["trail_stop"] == 5001.5 and moved["peak"] == 5004.0

    rising = {**p, "stop_loss": 5001.5, "trail_stop": 5001.5, "peak": 5004.0}
    held = atm.advance(rising, price=5004.0, ts_ms=3_000)                 # nothing new to pull up
    assert held["actions"] == [] and held["stop_loss"] == 5001.5

    further = atm.advance(rising, price=5006.0, ts_ms=3_000)
    assert further["actions"] == ["trail"] and further["stop_loss"] == 5003.5

    tiny = atm.advance(rising, price=5004.25, ts_ms=3_000)                # a 1-tick creep is below step
    assert tiny["actions"] == [] and tiny["stop_loss"] == 5001.5

    # A trail is not gated on the break-even trigger: two ticks of progress already lean the stop.
    fresh = atm.advance(make_plan(), price=5001.0, ts_ms=3_000)
    assert fresh["breakeven_done"] is False and fresh["actions"] == ["trail"]
    assert fresh["stop_loss"] == 4998.5


def test_a_short_plan_trails_the_other_way():
    p = {**make_plan(side="sell"), "breakeven_done": True, "stop_loss": 5000.0, "peak": 4998.0}
    moved = atm.advance(p, price=4995.0, ts_ms=3_000)
    assert moved["actions"] == ["trail"] and moved["stop_loss"] == 4997.5
    assert moved["trail_stop"] == 4997.5 and moved["peak"] == 4995.0


def test_the_clock_closes_the_plan_at_the_print_it_runs_out_on():
    timed = atm.clean_template({**runner(), "time_stop_min": 30, "trail_ticks": 0,
                                "breakeven_ticks": 0})
    p = make_plan(template=timed, ts_ms=1_000_000)
    early = atm.advance(p, price=5001.0, ts_ms=1_000_000 + 29 * 60_000)
    assert early["exit"] is None and early["minutes_open"] == 29.0
    late = atm.advance(p, price=5001.5, ts_ms=1_000_000 + 30 * 60_000)
    assert late["exit"] == {"reason": "time_stop", "price": 5001.5}
    assert late["actions"][-1] == "time_stop"
    assert late["minutes_open"] == 30.0


@pytest.mark.parametrize("state,price,reason,levels", [
    (None, 5000.0, "no plan is attached to this position", (None, None)),
    ({}, 5000.0, "no plan is attached to this position", (None, None)),
    ({"ok": False}, 5000.0, "no plan is attached to this position", (None, None)),
    ({"ok": True, "status": "done", "stop_loss": 4998.0, "take_profit": 5008.0}, 5000.0,
     "that plan is finished", (4998.0, 5008.0)),
    ({"ok": True, "status": "live", "side": "buy", "entry": ENTRY}, None,
     "the print has no usable price", (None, None)),
    ({"ok": True, "status": "live", "side": "nonsense", "entry": ENTRY}, 5000.0,
     "the plan has no side or no entry price to measure from", (None, None)),
    ({"ok": True, "status": "live", "side": "buy", "entry": 0}, 5000.0,
     "the plan has no side or no entry price to measure from", (None, None)),
])
def test_advance_refuses_with_a_sentence_and_leaves_the_plan_alone(state, price, reason, levels):
    # §148 T1-D12: the levels are asserted per row, not echoed back. The old line compared the step
    # against `(state or {}).get("stop_loss")`, which is None on both sides for four of these rows —
    # "leaves the plan alone" was untested exactly where nothing was there to leave alone. Now a row
    # that carries levels must return with the same ones, and a row without any must gain none.
    step = atm.advance(state, price=price, ts_ms=1_000)
    assert step["ok"] is False and step["reason"] == reason
    assert step["changed"] is False and step["actions"] == [] and step["exit"] is None
    assert (step["stop_loss"], step["take_profit"]) == levels


def test_advance_is_json_ready_on_a_full_plan():
    step = atm.advance(make_plan(), price=5002.0, ts_ms=5_000)
    assert set(step) == {"ok", "reason", "changed", "stop_loss", "take_profit", "trail_stop", "peak",
                         "breakeven_done", "partial_done", "exit", "actions", "ticks", "minutes_open"}
    json.dumps(step)
    assert atm.ticks_for(make_plan(), 5001.0) == 4.0
    assert atm.ticks_for(make_plan(side="sell"), 4999.0) == 4.0
    assert atm.ticks_for(None, 5000.0) is None
    assert atm.minutes_open({"opened_ms": 1_000}, 61_000) == 1.0
    assert atm.minutes_open({}, 61_000) == 0.0


def test_better_stop_only_accepts_a_move_in_the_positions_favour():
    assert atm.better_stop("buy", 4998.0, 4999.0, tick_size=TICK) == 4999.0
    assert atm.better_stop("buy", 4998.0, 4998.25, tick_size=TICK) == 4998.25   # exactly one step is a move
    assert atm.better_stop("buy", 4998.0, 4997.0, tick_size=TICK) is None       # never widens
    assert atm.better_stop("buy", 4998.0, 4998.25, step_ticks=2, tick_size=TICK) is None
    assert atm.better_stop("buy", 4998.0, 4998.5, step_ticks=2, tick_size=TICK) == 4998.5
    assert atm.better_stop("sell", 5002.0, 5001.0, tick_size=TICK) == 5001.0
    assert atm.better_stop("sell", 5002.0, 5003.0, tick_size=TICK) is None
    assert atm.better_stop("buy", None, 4999.0, tick_size=TICK) == 4999.0       # no stop yet: it is the stop
    assert atm.better_stop("buy", 4998.0, "junk", tick_size=TICK) is None
    assert atm.better_stop("sideways", 4998.0, 4999.0, tick_size=TICK) is None
