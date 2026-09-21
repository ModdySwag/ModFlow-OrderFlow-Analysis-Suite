"""ATM plans: templates, brackets, break-even, trailing stops and time stops — pure arithmetic.

An **order template** is the plan a trader repeats: how big, where the stop sits, where the target
sits, when the stop moves to break-even, how it trails, how long the trade may live, and whether
part of it comes off at one R. This module owns that vocabulary and turns an entry price into
**legs** — an entry, a stop, a target and optionally a partial — that belong to one OCO group, so
the legs are siblings and only one of them can be the reason the position leaves.

Everything here is pure: plain dicts in, plain dicts out. No config file, no account, no clock, no
IO. The tick grid is the only unit that matters — every price returned has been rounded onto the
instrument's tick, and every distance a template names is counted in ticks, the unit the paper
account and the trade journal already use.

Nothing here raises. A plan that cannot be built comes back as ``{"ok": False, "reason": "<one
plain sentence>"}``: the ladder shows the sentence, the account refuses the order, and a test can
pin the words.

    template = template_of(DEFAULTS, "runner")
    p = plan("buy", template["size"], 5000.0, template, tick_size=0.25)
    p["stop_loss"], p["take_profit"], p["partial"]["size"]        # 4998.0, 5006.0, 1.0
    step = advance(p, price=5002.0, ts_ms=1_000)                  # the print reached 2R
    step["actions"]                                               # ['arm_breakeven', 'move_stop']
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: Every field a template carries. ``clean`` never invents one it does not know.
TEMPLATE_FIELDS = ("id", "name", "size", "stop_ticks", "target_ticks", "breakeven_ticks",
                   "trail_ticks", "trail_step_ticks", "time_stop_min", "partial_ticks", "partial_pct")

#: The shape a template has before anyone fills it in: one contract, no stop, no target.
BLANK_TEMPLATE: dict[str, Any] = {
    "id": "", "name": "", "size": 1.0,
    "stop_ticks": 0, "target_ticks": 0, "breakeven_ticks": 0,
    "trail_ticks": 0, "trail_step_ticks": 1,
    "time_stop_min": 0, "partial_ticks": 0, "partial_pct": 50,
}

#: The templates the build ships with. A rough day-trading spread rather than a claim about edge:
#: one scalp with no management, one managed trade that pays half at one R, one runner that
#: trails and gives itself a clock.
SHIPPED_TEMPLATES: tuple[dict[str, Any], ...] = (
    {"id": "scalp", "name": "Scalp", "size": 1.0,
     "stop_ticks": 8, "target_ticks": 12, "breakeven_ticks": 0,
     "trail_ticks": 0, "trail_step_ticks": 1, "time_stop_min": 0,
     "partial_ticks": 0, "partial_pct": 50},
    {"id": "intraday", "name": "Intraday", "size": 2.0,
     "stop_ticks": 8, "target_ticks": 20, "breakeven_ticks": 6,
     "trail_ticks": 0, "trail_step_ticks": 1, "time_stop_min": 0,
     "partial_ticks": 8, "partial_pct": 50},
    {"id": "runner", "name": "Runner", "size": 2.0,
     "stop_ticks": 8, "target_ticks": 32, "breakeven_ticks": 8,
     "trail_ticks": 10, "trail_step_ticks": 2, "time_stop_min": 30,
     "partial_ticks": 8, "partial_pct": 50},
)

#: The feature's settings block: which template the next click uses, and the templates themselves.
DEFAULTS: dict[str, Any] = {
    "active": "",
    "templates": [dict(t) for t in SHIPPED_TEMPLATES],
}

#: A plan's status. ``live`` while the position is open; ``done`` once it has left, with the outcome.
PLAN_STATUSES = ("live", "done")

#: The reasons this module can name for leaving, plus the two the account already books.
EXIT_REASONS = ("stop_loss", "take_profit", "time_stop")
PLAN_OUTCOMES = ("stop_loss", "take_profit", "time_stop", "flatten", "flip", "unknown")

#: Caught in ``clean``: a template list bigger than this is a config accident, not a wish.
MAX_TEMPLATES = 12
#: Ticks are rounded here on the way out, exactly as the paper account rounds its PnL.
TICK_DECIMALS = 10


def _number(value: Any) -> Optional[float]:
    """``value`` as a finite float, or ``None`` when it is not one. Never raises."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _positive(value: Any) -> Optional[float]:
    """``value`` as a positive float, or ``None``."""
    out = _number(value)
    return out if out is not None and out > 0 else None


def _count(value: Any, default: float = 0.0) -> float:
    """A size: a positive number, clamped to something a ticket could actually send."""
    out = _number(value)
    if out is None or out <= 0:
        return default
    return min(out, 10_000.0)


def _ticks(value: Any, default: int = 0, *, hi: int = 100_000) -> int:
    """A distance in ticks: a whole number of ticks, never negative, capped. Junk becomes ``default``."""
    out = _number(value)
    if out is None:
        return default
    return max(0, min(int(round(out)), hi))


def _text(value: Any) -> str:
    """A vocabulary word, lower-cased — accepts the app's enums as well as plain strings."""
    return str(getattr(value, "value", value)).strip().lower()


def _ident(value: Any) -> str:
    """A template id: lower case, letters, digits, hyphen and underscore, at most 24 characters."""
    raw = str(getattr(value, "value", value) or "").strip().lower()
    return "".join(ch for ch in raw if ch.isalnum() or ch in "-_")[:24]


def round_to_tick(price: Any, tick_size: Any) -> Optional[float]:
    """``price`` snapped onto the tick grid, or ``None`` when either argument is unusable.

    Half rounds away from zero (a price and its mirror round alike), and the product is rounded
    again at :data:`TICK_DECIMALS` so 0.05-tick arithmetic never leaks 5000.250000000001.
    """
    px = _number(price)
    tick = _positive(tick_size)
    if px is None or tick is None:
        return None
    steps = math.floor(abs(px) / tick + 0.5)
    return round(math.copysign(steps, px) * tick, TICK_DECIMALS)


def side_of(value: Any) -> str:
    """``'buy'`` / ``'sell'`` from the app's vocabulary, or ``''`` when it is neither."""
    side = _text(value)
    return side if side in ("buy", "sell") else ""


def direction_of(side: Any) -> int:
    """``+1`` for a long, ``-1`` for a short, ``0`` for anything else."""
    return 1 if side_of(side) == "buy" else (-1 if side_of(side) == "sell" else 0)


# ══════════════════════════════════════════════════════════════
# Templates and the settings block
# ══════════════════════════════════════════════════════════════

def clean_template(raw: Any) -> dict[str, Any]:
    """Coerce anything into a template. Unknown keys drop, junk is defaulted, nothing raises.

    A template with no usable id comes back with ``id == ""``; ``clean`` drops those, because a
    template nobody can name is a template nobody can select.
    """
    src = raw if isinstance(raw, dict) else {}
    out = dict(BLANK_TEMPLATE)
    out["id"] = _ident(src.get("id"))
    out["name"] = str(src.get("name") or out["id"] or "").strip()[:24]
    out["size"] = _count(src.get("size"), 1.0)
    out["stop_ticks"] = _ticks(src.get("stop_ticks"))
    out["target_ticks"] = _ticks(src.get("target_ticks"))
    out["breakeven_ticks"] = _ticks(src.get("breakeven_ticks"))
    out["trail_ticks"] = _ticks(src.get("trail_ticks"))
    out["trail_step_ticks"] = max(1, _ticks(src.get("trail_step_ticks"), 1))
    out["time_stop_min"] = _ticks(src.get("time_stop_min"), hi=24 * 60)
    pct = _number(src.get("partial_pct"))
    out["partial_pct"] = int(min(99, max(0, round(pct)))) if pct is not None else 0
    # A partial without a level to take it at is a template that means nothing, so the pair is
    # all-or-nothing: no level, no partial — and a partial with a 0% wish takes nothing off.
    out["partial_ticks"] = _ticks(src.get("partial_ticks"))
    if out["partial_ticks"] <= 0 or out["partial_pct"] <= 0:
        out["partial_ticks"] = 0
        out["partial_pct"] = 0
    return out


def clean(patch: Any) -> dict[str, Any]:
    """Coerce an incoming settings patch onto :data:`DEFAULTS`. Never raises; returns only the block.

    A patch with no usable templates keeps the shipped set — the ladder's buttons must not vanish
    because a config file was hand-edited into nonsense. ``active`` survives only when a template
    with that id is in the block: the next click can never point at nothing.
    """
    out: dict[str, Any] = {"active": "", "templates": [dict(t) for t in DEFAULTS["templates"]]}
    if not isinstance(patch, dict):
        return out
    if isinstance(patch.get("templates"), list):
        cleaned = [clean_template(t) for t in patch["templates"] if isinstance(t, dict)][:MAX_TEMPLATES]
        kept = [t for t in cleaned if t["id"]]
        if kept:
            out["templates"] = kept
    active = _ident(patch.get("active"))
    if active and any(t["id"] == active for t in out["templates"]):
        out["active"] = active
    return out


def template_of(cfg: Any, template_id: Any) -> Optional[dict[str, Any]]:
    """The template named ``template_id`` in a settings block, or ``None``. Never raises."""
    wanted = _ident(template_id)
    if not wanted:
        return None
    block = cfg if isinstance(cfg, dict) else {}
    for entry in block.get("templates") or []:
        if isinstance(entry, dict) and clean_template(entry)["id"] == wanted:
            found = clean_template(entry)
            return found
    return None


def describe(template: Any) -> str:
    """One plain sentence for a template — the ladder's status line and every tooltip."""
    t = clean_template(template)
    bits = [f"{(t['size']):g} contract" + ("" if t["size"] == 1 else "s")]
    bits.append(f"stop {t['stop_ticks']}t" if t["stop_ticks"] else "no stop")
    bits.append(f"target {t['target_ticks']}t" if t["target_ticks"] else "no target")
    if t["breakeven_ticks"]:
        bits.append(f"break-even at {t['breakeven_ticks']}t")
    if t["trail_ticks"]:
        bits.append(f"trail {t['trail_ticks']}t/{t['trail_step_ticks']}t")
    if t["time_stop_min"]:
        bits.append(f"time stop {t['time_stop_min']} min")
    if t["partial_ticks"]:
        bits.append(f"{t['partial_pct']}% off at {t['partial_ticks']}t")
    return f"{t['name'] or t['id'] or 'plan'} — " + ", ".join(bits)


# ══════════════════════════════════════════════════════════════
# Entry price → legs
# ══════════════════════════════════════════════════════════════

def _refusal(reason: str) -> dict[str, Any]:
    """The one shape every refusal takes: a sentence a person could read out loud."""
    return {"ok": False, "reason": reason}


def partial_size(size: Any, pct: Any) -> float:
    """How much of ``size`` comes off at the partial: whole contracts, and never the last one.

    A one-contract position cannot be halved in a futures book, so a partial needs size 2 or more;
    below that this returns 0 and the plan simply has no partial leg.
    """
    total = _count(size)
    share = _number(pct) or 0.0
    if total < 2 or share <= 0:
        return 0.0
    take = math.floor(total * min(share, 99.0) / 100.0)
    return float(min(take, total - 1)) if take >= 1 else 0.0


def plan(side: Any, size: Any, entry: Any, template: Any, *, tick_size: Any = 0.01,
         kind: str = "market", ts_ms: Any = 0, group: str = "") -> dict[str, Any]:
    """Turn an entry into a bracket: the entry leg, the stop, the target, and any partial.

    ``entry`` is the price the position will actually be opened at — the fill price, which is why
    the account builds the plan when the order fills rather than when it is sent. A limit that
    rests for an hour must be stopped 8 ticks from *its* fill, not from the click that placed it.

    Returns the plan, or a refusal dict. Every level is rounded onto the tick grid, and every
    distance is signed from the entry (negative is against the position) so a renderer never has to
    know which way round a trade is.
    """
    side_name = side_of(side)
    if not side_name:
        return _refusal("a plan needs a side — 'buy' or 'sell'")
    amount = _count(size)
    if amount <= 0:
        return _refusal("a plan needs a size above 0")
    tick = _positive(tick_size)
    if tick is None:
        # Every level below is measured on this grid, so guessing one would put the stop on a price
        # the instrument cannot trade. Refuse instead.
        return _refusal("a plan needs the instrument's tick size — that one is not usable")
    fill = round_to_tick(entry, tick)
    if fill is None or fill <= 0:
        return _refusal("a plan needs the entry price it will fill at — that price is not usable")
    t = clean_template(template)
    if not (t["stop_ticks"] or t["target_ticks"] or t["time_stop_min"] or t["trail_ticks"]):
        return _refusal("that template names no stop, target, trail or clock — there is no plan in it")

    direction = direction_of(side_name)
    exit_side = "sell" if direction > 0 else "buy"
    against = -1 if direction > 0 else 1

    def level(ticks: int, sign: int) -> Optional[float]:
        """A price ``ticks`` away from the entry in the direction ``sign``, on the tick grid."""
        if ticks <= 0:
            return None
        return round_to_tick(fill + sign * ticks * tick, tick)

    stop = level(t["stop_ticks"], against)
    target = level(t["target_ticks"], direction)
    breakeven = level(t["breakeven_ticks"], direction)
    take = partial_size(amount, t["partial_pct"])
    partial_price = level(t["partial_ticks"], direction) if (take and t["partial_ticks"]) else None
    if take and partial_price is None:
        take = 0.0

    legs: list[dict[str, Any]] = [{"name": "entry", "role": "entry", "side": side_name, "kind": _text(kind) or "market",
                                   "size": amount, "price": fill, "ticks": 0}]
    if partial_price is not None:
        legs.append({"name": "partial", "role": "reduce", "side": exit_side, "kind": "limit",
                     "size": take, "price": partial_price,
                     "ticks": t["partial_ticks"] * direction})
    if stop is not None:
        legs.append({"name": "stop", "role": "exit", "side": exit_side, "kind": "stop",
                     "size": amount, "price": stop, "ticks": -t["stop_ticks"] * direction})
    if target is not None:
        legs.append({"name": "target", "role": "exit", "side": exit_side, "kind": "limit",
                     "size": amount, "price": target, "ticks": t["target_ticks"] * direction})

    rr = (t["target_ticks"] / t["stop_ticks"]) if t["stop_ticks"] else 0.0
    minutes = int(t["time_stop_min"])
    stamp = _number(ts_ms)
    out: dict[str, Any] = {
        "ok": True,
        "reason": "",
        "group": _ident(group) or f"atm-{t['id'] or 'plan'}",
        "template": dict(t),
        "text": describe({**t, "size": amount}),
        "side": side_name,
        "direction": direction,
        "kind": _text(kind) or "market",
        "size": amount,
        "entry": fill,
        "tick_size": tick,
        "stop_ticks": int(t["stop_ticks"]),
        "target_ticks": int(t["target_ticks"]),
        "stop_loss": stop,
        "take_profit": target,
        "breakeven_ticks": int(t["breakeven_ticks"]),
        "breakeven_price": breakeven,
        "trail_ticks": int(t["trail_ticks"]),
        "trail_step_ticks": int(t["trail_step_ticks"]),
        "trail_stop": None,
        "peak": fill,
        "time_stop_min": minutes,
        "time_stop_at_ms": (int(stamp) + minutes * 60_000) if (minutes and stamp and stamp > 0) else None,
        "partial": ({"size": take, "ticks": int(t["partial_ticks"]), "price": partial_price,
                     "pct": int(t["partial_pct"])} if take and partial_price is not None else None),
        "legs": legs,
        "rr": round(rr, 4),
        "breakeven_done": False,
        "partial_done": False,
        "status": "live",
        "outcome": "",
        "opened_ms": int(stamp) if stamp and stamp > 0 else 0,
        "closed_ms": 0,
    }
    logger.debug("atm %s: %s plan %s — stop %s target %s partial %s", side_name, t["id"] or "plan",
                 out["group"], stop, target, out["partial"])
    return out


def legs(state: Any) -> list[dict[str, Any]]:
    """The plan's legs as copies, in the order they were built — safe to hand to a renderer."""
    src = state if isinstance(state, dict) else {}
    return [dict(leg) for leg in src.get("legs") or [] if isinstance(leg, dict)]


def oco(state: Any) -> dict[str, Any]:
    """The one-cancels-other group over a plan's legs.

    A bracket is a pair of intents, so the group is what makes the pair behave as siblings: when one
    leg of the group is the reason the position leaves, every *other* working leg in the group is
    cancelled rather than left resting on a position that no longer exists. ``cancels`` names them.

    §148 T1-D9: this is the read model of that rule — a caller's table of which legs a fill takes
    with it. The paper account does not walk it: it cancels by the orders' own ``group``
    (``paper._cancel_group``), which is the same group this function names.
    """
    src = state if isinstance(state, dict) else {}
    members = [str(leg.get("name")) for leg in legs(src)]
    resting = [name for name in members if name not in ("entry",)]
    return {
        "group": str(src.get("group") or ""),
        "legs": members,
        "resting": resting,
        "cancels": {name: [other for other in resting if other != name] for name in members},
    }


def siblings(state: Any, leg_name: Any) -> list[str]:
    """The legs of the same group that must be cancelled when ``leg_name`` fills (§148 T1-D9: the
    paper account cancels by group instead — see :func:`oco`)."""
    return list(oco(state)["cancels"].get(str(leg_name), []))


# ══════════════════════════════════════════════════════════════
# Managing the plan, print by print
# ══════════════════════════════════════════════════════════════

def ticks_for(state: Any, price: Any) -> Optional[float]:
    """How far ``price`` is from the plan's entry, in ticks, signed with the position.

    Positive is in the position's favour, negative is against it — the number a person reads as
    "+6 ticks" or "−8 ticks" without having to remember which way they are trading.
    """
    src = state if isinstance(state, dict) else {}
    px = _number(price)
    entry = _positive(src.get("entry"))
    tick = _positive(src.get("tick_size")) or 0.01
    direction = direction_of(src.get("side"))
    if px is None or entry is None or not direction:
        return None
    return round((px - entry) * direction / tick, 4)


def time_stop_hit(time_stop_at_ms: Any, ts_ms: Any) -> bool:
    """Has the plan's clock run out? An absent clock, or a stamp of 0 (no tape time), never fires."""
    deadline = _number(time_stop_at_ms)
    stamp = _number(ts_ms)
    return bool(deadline and deadline > 0 and stamp and stamp > 0 and stamp >= deadline)


def minutes_open(state: Any, ts_ms: Any) -> float:
    """How long the position has been open by the tape's clock, in minutes (0 when unknown)."""
    src = state if isinstance(state, dict) else {}
    opened = _number(src.get("opened_ms"))
    stamp = _number(ts_ms)
    if not opened or not stamp or stamp <= opened:
        return 0.0
    return round((stamp - opened) / 60_000.0, 3)


def better_stop(side: Any, current: Any, candidate: Any, *, step_ticks: int = 1,
                tick_size: Any = 0.01) -> Optional[float]:
    """Which stop to carry: the one that has moved in the position's favour, or ``None`` to hold.

    A stop only ever ratchets — it never widens — and it only moves when the move is worth at least
    ``step_ticks``, so a trail that jitters by a tick a print does not rewrite the bracket on every
    print. Equal is "no move".
    """
    new = round_to_tick(candidate, tick_size)
    old = round_to_tick(current, tick_size)
    if new is None:
        return None
    if old is None:
        return new
    tick = _positive(tick_size) or 0.01
    step = max(1, int(step_ticks or 1)) * tick
    direction = direction_of(side)
    if not direction:
        return None
    gain = (new - old) * direction
    return new if gain >= step - 1e-9 else None


def trail_candidate(state: Any, peak: Any = None, *, tick_size: Any = None) -> Optional[float]:
    """Where the trail would put the stop from the best price seen so far, or ``None``."""
    src = state if isinstance(state, dict) else {}
    ticks = int(_number(src.get("trail_ticks")) or 0)
    if ticks <= 0:
        return None
    tick = _positive(tick_size) or _positive(src.get("tick_size")) or 0.01
    top = _number(peak)
    if top is None:
        top = _number(src.get("peak"))
    if top is None:
        top = _positive(src.get("entry"))
    if top is None:
        return None
    direction = direction_of(src.get("side"))
    if not direction:
        return None
    return round_to_tick(top - direction * ticks * tick, tick)


def finish(state: Any, outcome: str, *, ts_ms: Any = 0) -> dict[str, Any]:
    """The plan after the position has left: status ``done``, the outcome named, the legs settled."""
    out = dict(state) if isinstance(state, dict) else {}
    out["status"] = "done"
    out["outcome"] = outcome if outcome in PLAN_OUTCOMES else "unknown"
    stamp = _number(ts_ms)
    out["closed_ms"] = int(stamp) if stamp and stamp > 0 else 0
    out["exit"] = None
    return out


def advance(state: Any, *, price: Any, ts_ms: Any = 0, tick_size: Any = None,
            levels: bool = True) -> dict[str, Any]:
    """One print's worth of plan management: break-even, the trail, the clock.

    Returns the plan's *new* numbers rather than mutating the caller's dict, so the account can log
    what it did and a test can pin it:

    ``stop_loss`` / ``take_profit``
        where the legs stand now (``None`` when the leg does not exist)
    ``actions``
        ``move_stop``, ``arm_breakeven``, ``trail``, ``time_stop`` — what this print changed
    ``exit``
        ``{"reason": "time_stop", "price": <the print>}`` when the clock has run out, else ``None``

    A print with no usable price, a finished plan or a flat side is refused with a sentence and an
    unchanged result. The price levels themselves are *not* checked here: the account's own exit
    check owns that, and it runs with the stop this function has just moved.

    ``levels=False`` runs the clock only (§148 T1-D7): the break-even move and the trail are left
    alone, because those two *are* levels and the user owns them once the exits have been edited by
    hand. The time stop is a rule, not a level, so it still fires.
    """
    out: dict[str, Any] = {
        "ok": False, "reason": "no plan is attached to this position", "changed": False,
        "stop_loss": None, "take_profit": None, "trail_stop": None, "peak": None,
        "breakeven_done": False, "partial_done": False, "exit": None, "actions": [],
        "ticks": None, "minutes_open": 0.0,
    }
    if not isinstance(state, dict) or not state.get("ok"):
        return out
    src = dict(state)
    if str(src.get("status") or "live") != "live":
        out["reason"] = "that plan is finished"
        out["stop_loss"], out["take_profit"] = src.get("stop_loss"), src.get("take_profit")
        return out
    px = _number(price)
    if px is None or px <= 0:
        out["reason"] = "the print has no usable price"
        out["stop_loss"], out["take_profit"] = src.get("stop_loss"), src.get("take_profit")
        return out
    side_name = side_of(src.get("side"))
    entry = _positive(src.get("entry"))
    if not side_name or entry is None:
        out["reason"] = "the plan has no side or no entry price to measure from"
        out["stop_loss"], out["take_profit"] = src.get("stop_loss"), src.get("take_profit")
        return out

    tick = _positive(tick_size) or _positive(src.get("tick_size")) or 0.01
    direction = direction_of(side_name)
    stop_now = _positive(src.get("stop_loss"))
    target = _positive(src.get("take_profit"))
    actions: list[str] = []

    # The best price the position has seen — what a trail hangs off, and the honest record of how
    # far a trade got even when it ends badly.
    peak = _positive(src.get("peak")) or entry
    peak = max(peak, px) if direction > 0 else min(peak, px)

    breakeven_done = bool(src.get("breakeven_done"))
    be_ticks = int(_number(src.get("breakeven_ticks")) or 0)
    excursion = (px - entry) * direction / tick
    if levels and be_ticks and not breakeven_done and excursion >= be_ticks - 1e-9:
        candidate = better_stop(side_name, stop_now, entry, tick_size=tick)
        if candidate is not None:
            stop_now = candidate
            actions.extend(["arm_breakeven", "move_stop"])
        breakeven_done = True

    trail_stop = _positive(src.get("trail_stop"))
    candidate = trail_candidate(src, peak, tick_size=tick)
    if levels and candidate is not None:
        moved = better_stop(side_name, stop_now, candidate,
                           step_ticks=int(_number(src.get("trail_step_ticks")) or 1), tick_size=tick)
        if moved is not None:
            stop_now, trail_stop = moved, moved
            actions.append("trail")

    out.update({"ok": True, "reason": "", "stop_loss": stop_now, "take_profit": target,
                "trail_stop": trail_stop, "peak": peak, "breakeven_done": breakeven_done,
                "partial_done": bool(src.get("partial_done")), "actions": list(actions),
                "ticks": ticks_for({**src, "entry": entry, "side": side_name, "tick_size": tick}, px),
                "minutes_open": minutes_open(src, ts_ms),
                "changed": bool(actions)})
    if time_stop_hit(src.get("time_stop_at_ms"), ts_ms):
        out["actions"] = actions + ["time_stop"]
        out["exit"] = {"reason": "time_stop", "price": px}
    return out
