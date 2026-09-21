"""
Order-flow alert rules (the reference layout "Alerts" equivalent).

the reference layout lets you attach alert conditions to order-flow events (big trade, sweep,
iceberg, stop run, speed of tape, delta divergence) and route them to a sound,
a popup or a log. This is the same idea for our feed: rules are plain dicts,
evaluated against every detection the FeatureHub produces, with per-rule
cooldowns and per-rule minimum-size filters so the alert list stays readable.

Rules are persisted in the desktop config file, so the GUI can manage them.

Two things a rule can carry on top of its kind and its params, both additive — a rule that sets
neither behaves exactly as it always has:

* ``conditions`` + ``match`` — a second and third reading that has to agree before the rule fires
  (``evaluate_conditions``), because "a sweep" and "a sweep into a book that is leaning the other
  way" are different trades;
* ``context`` — the rule asks for a short evidence snapshot to ride its notification
  (``context_block``), so the channel that wakes you up carries what actually happened instead of
  one sentence.
"""

from __future__ import annotations

import copy
import csv
import io
import logging
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

logger = logging.getLogger(__name__)

KINDS = (
    "big_trade", "block_trade", "sweep", "stop_run", "iceberg",
    "speed_spike", "cvd_divergence", "heat_pull", "heat_stack", "wall",
    "stacked_imbalance", "intent_pressure", "pulled_size", "trapped_traders",
    "vwap_cross", "depth_execution", "depth_refill",
    # the depth map's own kind (P1-6): a level that keeps holding. It is what a heatmap level alert
    # creates with "alert: if this level holds", and `wall_age` events carry `held_ms`.
    "wall_age",
    # level reads (fold-in plan §3): unfinished auctions + node runs, fed from closed bars
    "unfinished_business", "node_zone",
    # the area profile's hand-off (fold-in plan §3 / A3): "watch this level" — the engine fires
    # when price RETURNS into the rule's own at_price band. Emitted by `evaluate_touch`, which
    # the hub's tick path calls; no detector payload is involved.
    "level_touch",
    # the level radar (fold-in plan §4 / G1): every tracker transition — armed, approaching,
    # defended, confirmed, spent, failed — dispatches as this kind from `hub.on_tick`.
    "radar_level",
)

DEFAULT_RULES: list[dict[str, Any]] = [
    {"id": "big-default", "name": "Big trade", "kind": "big_trade", "enabled": True,
     "params": {"min_multiple": 1.5, "sides": ["buy", "sell"]}, "cooldown_s": 10, "channels": ["ui", "telegram"]},
    {"id": "blocks", "name": "Block trade", "kind": "block_trade", "enabled": True,
     "params": {"min_multiple": 3.0}, "cooldown_s": 10, "channels": ["ui", "telegram"]},
    {"id": "sweeps", "name": "Sweep ≥5 levels", "kind": "sweep", "enabled": True,
     "params": {"min_levels": 5}, "cooldown_s": 15, "channels": ["ui", "telegram"]},
    {"id": "stopruns", "name": "Stop run", "kind": "stop_run", "enabled": True,
     "params": {"min_ticks": 12.0}, "cooldown_s": 30, "channels": ["ui", "telegram"]},
    {"id": "icebergs", "name": "Iceberg (inferred)", "kind": "iceberg", "enabled": True,
     "params": {"min_fills": 4}, "cooldown_s": 30, "channels": ["ui"]},
    {"id": "speed", "name": "Speed of tape spike", "kind": "speed_spike", "enabled": True,
     "params": {"min_zscore": 3.0}, "cooldown_s": 20, "channels": ["ui"]},
    {"id": "cvd-div", "name": "CVD divergence", "kind": "cvd_divergence", "enabled": True,
     "params": {"kinds": ["bearish", "bullish"], "min_strength": 50}, "cooldown_s": 60, "channels": ["ui", "telegram"]},
    {"id": "heat-pull", "name": "Liquidity pulled near price", "kind": "heat_pull", "enabled": True,
     "params": {}, "cooldown_s": 30, "channels": ["ui"]},
    {"id": "heat-stack", "name": "Liquidity stacking", "kind": "heat_stack", "enabled": True,
     "params": {}, "cooldown_s": 30, "channels": ["ui"]},
    {"id": "stacked-imb", "name": "Stacked imbalance ≥3 levels", "kind": "stacked_imbalance", "enabled": True,
     "params": {"min_levels": 3, "min_volume": 0.0}, "cooldown_s": 60, "channels": ["ui", "telegram"]},
    # participants' intent (order-book reading) — UI by default, quieter than the tape rules
    {"id": "vwap-cross", "name": "Price crosses VWAP", "kind": "vwap_cross", "enabled": True,
     "params": {"min_ticks": 0.0}, "cooldown_s": 60, "channels": ["ui"]},
    {"id": "depth-execution", "name": "Trade eats resting depth", "kind": "depth_execution",
     "enabled": True, "params": {"min_share": 0.3}, "cooldown_s": 30, "channels": ["ui"]},
    {"id": "depth-refill", "name": "Level refills after being eaten", "kind": "depth_refill",
     "enabled": True, "params": {"min_share": 0.3}, "cooldown_s": 45, "channels": ["ui"]},
    {"id": "intent-pressure", "name": "Book pressure ≥80% of normal", "kind": "intent_pressure", "enabled": True,
     "params": {"min_pct": 80.0}, "cooldown_s": 60, "channels": ["ui"]},
    {"id": "intent-pull", "name": "Large size pulled near price", "kind": "pulled_size", "enabled": True,
     "params": {"min_size": 0.0, "max_distance_ticks": 10.0}, "cooldown_s": 30, "channels": ["ui"]},
    {"id": "intent-trap", "name": "Break failed — side trapped", "kind": "trapped_traders", "enabled": True,
     "params": {"min_beyond_ticks": 3.0}, "cooldown_s": 60, "channels": ["ui"]},
    # level reads (fold-in plan §3): context, not noise — UI-only by default
    {"id": "unfinished", "name": "Unfinished business", "kind": "unfinished_business", "enabled": True,
     "params": {"min_arms": 1}, "cooldown_s": 60, "channels": ["ui"]},
    {"id": "nodes", "name": "Node formed", "kind": "node_zone", "enabled": True,
     "params": {"min_count": 2}, "cooldown_s": 60, "channels": ["ui"]},
    # level radar (fold-in plan §4 / G1): the transition worth interrupting for is a level that
    # held — arming and approach chatter stays in the Radar column and the Alerts log.
    {"id": "radar-held", "name": "Radar level held", "kind": "radar_level", "enabled": True,
     "params": {"states": ["defended", "confirmed"]}, "cooldown_s": 60, "channels": ["ui"]},
]


# ══════════════════════════════════════════════════════════════
# The feature's settings block
# ══════════════════════════════════════════════════════════════
#
# Registered by the parent as ``atlas.alert_builder``. Everything here governs the *evidence block*
# a rule can ask for and how many conditions a rule may carry; the rules themselves stay in
# ``atlas.alert_rules``. A rule opts into a block of its own with a ``context`` key, so a fresh
# install that changes nothing sends exactly the notifications it sent before this existed.

DEFAULTS: dict[str, Any] = {
    #: The feature's master switch. Off = no rule gets a block, whatever the rule asks for.
    "context_enabled": True,
    #: "text" (lines a human reads) or "csv" (the same readings as section,key,value rows).
    "context_format": "text",
    #: Hard character cap on one block, marker and all. 360 characters is ~6 short lines: enough for
    #: the trigger, the window's delta, the biggest prints and the nearest walls on one phone screen.
    "context_max_chars": 360,
    #: How many of the window's biggest prints the block names.
    "context_prints": 3,
    #: How many of the nearest resting levels it names.
    "context_levels": 3,
    #: The window the delta and the biggest prints are measured over.
    "context_window_ms": 60_000,
    #: The channels a block may ride. "ui" is deliberately absent: the screen already shows the
    #: event, the block is for the delivery that has to stand on its own. Add it to also carry one
    #: in the app's own alert payloads.
    "context_channels": ["telegram", "ntfy", "email", "webhook"],
    #: Ceiling on conditions per rule (a hand-edited config cannot make one evaluation expensive).
    "max_conditions": 8,
}

#: The channels a block may name. Everything the notebook of channels in the UI offers, minus the
#: ones that are not a delivery: the alert log is the app's own record.
CONTEXT_CHANNELS: tuple[str, ...] = ("ui", "telegram", "ntfy", "email", "webhook")

CONTEXT_FORMATS: tuple[str, ...] = ("text", "csv")

#: Hard ceiling on conditions per rule, whatever the settings say.
MAX_CONDITIONS = 12


def _num(value: Any, default: Optional[float] = None) -> Optional[float]:
    """A finite float, or ``default``. Booleans are not numbers here (True is not 1.0)."""
    if isinstance(value, bool) or value is None:
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if out == out and out not in (float("inf"), float("-inf")) else default


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("1", "true", "yes", "on"):
            return True
        if text in ("0", "false", "no", "off", ""):
            return False
    return default


def _int_in(value: Any, default: int, lo: int, hi: int) -> int:
    out = _num(value, None)
    return max(lo, min(hi, int(default if out is None else out)))


def _text_in(value: Any, default: str, allowed: Iterable[str]) -> str:
    text = str(value if value is not None else "").strip().lower()
    return text if text in tuple(allowed) else default


def _channel_list(value: Any) -> list[str]:
    """A channel list, in the block's own order, with unknown names dropped and duplicates removed."""
    raw = value if isinstance(value, (list, tuple, set)) else (
        [value] if isinstance(value, str) else [])
    out: list[str] = []
    for item in raw:
        name = str(item or "").strip().lower()
        if name in CONTEXT_CHANNELS and name not in out:
            out.append(name)
    return out


def _rule_channels(value: Any) -> list[str]:
    """A rule's delivery channels from whatever shape an older save wrote.

    A legacy config saved one channel as a bare string, and ``list("telegram")`` turned it into
    per-letter noise that matched no delivery — the rule went mute. Here a string is one or more
    channels (comma/space separated), a list keeps its entries, and anything else reads as the
    default surface. Unknown names are kept: delivery already intersects with what exists, and the
    authored text survives a save round-trip.
    """
    if isinstance(value, str):
        raw: list[Any] = [part for part in value.replace(",", " ").split(" ") if part]
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = []
    out = [str(item).strip().lower() for item in raw]
    return [name for name in out if name] or ["ui"]


def _rule_enabled(raw: dict[str, Any]) -> bool:
    """A rule's on/off flag, read the quiet way.

    ``bool("false")`` is True, so a rule a person had switched off in an older save came back on.
    Known spellings now read as written; a value that cannot be read as a flag at all reads off
    (quieter, and the builder shows it off); a rule that never carried the key stays on — that
    absence is the default, not an authored value.
    """
    if "enabled" not in raw:
        return True
    return _bool(raw.get("enabled"), False)


def _rule_params(value: Any) -> Any:
    """A rule's params: a dict as given, any other authored shape kept verbatim.

    A legacy string (``"min_multiple=5"``) used to make ``dict("...")`` raise the whole rules load
    away. Kept as authored instead: every reader goes through the unreadable-rule guard
    (``AlertEngine._note_unreadable``), so the rule reads as skipped-and-counted — quieter and
    visible — and the authored text survives a save round-trip.
    """
    if value is None:
        return {}
    return dict(value) if isinstance(value, dict) else value


def clean(patch: Any) -> dict[str, Any]:
    """Coerce an incoming settings patch onto ``DEFAULTS``: unknown keys dropped, nothing raises.

    The parent calls this with whatever the config store holds (or with a user's POST body), so it
    has to survive a string, a list, a half-filled dict — and it returns only this feature's block.
    """
    out = dict(DEFAULTS)
    out["context_channels"] = list(DEFAULTS["context_channels"])
    if not isinstance(patch, dict):
        return out
    if "context_enabled" in patch:
        out["context_enabled"] = _bool(patch.get("context_enabled"), DEFAULTS["context_enabled"])
    if "context_format" in patch:
        out["context_format"] = _text_in(patch.get("context_format"), DEFAULTS["context_format"],
                                         CONTEXT_FORMATS)
    if "context_max_chars" in patch:
        out["context_max_chars"] = _int_in(patch.get("context_max_chars"),
                                           DEFAULTS["context_max_chars"], 40, 2_000)
    if "context_prints" in patch:
        out["context_prints"] = _int_in(patch.get("context_prints"), DEFAULTS["context_prints"], 0, 10)
    if "context_levels" in patch:
        out["context_levels"] = _int_in(patch.get("context_levels"), DEFAULTS["context_levels"], 0, 10)
    if "context_window_ms" in patch:
        out["context_window_ms"] = _int_in(patch.get("context_window_ms"),
                                           DEFAULTS["context_window_ms"], 1_000, 3_600_000)
    if "context_channels" in patch:
        out["context_channels"] = _channel_list(patch.get("context_channels"))
    if "max_conditions" in patch:
        out["max_conditions"] = _int_in(patch.get("max_conditions"), DEFAULTS["max_conditions"],
                                        0, MAX_CONDITIONS)
    return out


def _payload_dict(payload: Any) -> dict[str, Any]:
    """Detections arrive as dicts or as small objects; read either without guessing."""
    if isinstance(payload, dict):
        return payload
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        try:
            return to_dict() or {}
        except Exception:
            return {}
    return getattr(payload, "__dict__", {}) or {}
def _price_of(payload: Any) -> Optional[float]:
    d = _payload_dict(payload)
    for key in ("price", "level", "px", "p"):
        v = d.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None
def _held_ms_of(payload: Any) -> Optional[float]:
    """How long a level had held when the event fired, when the event says so (wall_age does)."""
    d = _payload_dict(payload)
    v = d.get("held_ms")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None
def _scope_gates(params: dict[str, Any], payload: Any) -> list[dict[str, Any]]:
    """The two generic scopes a rule can carry — a bound price and a minimum hold — as verdicts.

    A rule may be bound to one price: the heatmap turns a selected level into an alert, and "at this
    level" has to mean the level, not the whole instrument. It may also be scoped by how long a level
    has held, for the same reason: the hold-alert asks for minutes, and an event that does not say
    how long it held is no evidence for it.

    One source of truth for both readers: ``AlertEngine.evaluate`` refuses an event that fails either
    scope, and the builder's rehearsal shows these rows, so a rule scoped to a level or a hold can
    never rehearse as firing on an event the live engine would refuse. Only the scopes the rule
    actually carries produce a row, and the comparisons are exactly the ones ``evaluate`` refuses on
    (same order, same short-circuits).
    """
    gates: list[dict[str, Any]] = []
    at_price = params.get("at_price")
    if at_price is not None:
        px = _price_of(payload)
        if px is None:
            gates.append({"gate": "at_price", "ok": False,
                          "detail": "the event carries no price, and this rule is scoped to one"})
        elif abs(px - float(at_price)) > float(params.get("at_tol", 0) or 0):
            tol = float(params.get("at_tol", 0) or 0)
            gates.append({"gate": "at_price", "ok": False,
                          "detail": f"the event is at {_fmt_price(px)} — away from the rule's own "
                                    f"level {_fmt_price(at_price)} (±{_fmt_price(tol)})"})
        else:
            gates.append({"gate": "at_price", "ok": True,
                          "detail": "the event's price stands at the rule's own level"})
    hold_s = float(params.get("min_age_s") or 0)
    if hold_s > 0:
        held_ms = _held_ms_of(payload)
        if held_ms is None:
            gates.append({"gate": "min_age_s", "ok": False,
                          "detail": f"the event does not say how long the level held, and this rule "
                                    f"asks for at least {_fmt_num(hold_s)} s"})
        elif held_ms < hold_s * 1000:
            gates.append({"gate": "min_age_s", "ok": False,
                          "detail": f"the level had held {_fmt_num(held_ms / 1000)} s — short of the "
                                    f"{_fmt_num(hold_s)} s this rule asks for"})
        else:
            gates.append({"gate": "min_age_s", "ok": True,
                          "detail": "the event says the level has held long enough"})
    return gates


# ══════════════════════════════════════════════════════════════
# Conditions — a rule that needs more than one reading to be true
# ══════════════════════════════════════════════════════════════
#
# A rule's ``kind`` says which detector it listens to and its ``params`` say how big that one reading
# has to be: one condition per rule. Real setups want a second one — a sweep only matters while the
# window's delta leans the same way; a wall only matters once the session is running — so a rule may
# also carry ``conditions``: a list of ``{kind, op, value, params}`` read against the same event (and
# the snapshot the engine holds, see ``ContextBuffer``), combined by ``match``: ``"all"`` or
# ``"any"``.
#
# Conservative by construction: an unknown condition kind, an op that does not belong to the kind's
# own class, a field the condition names but the event does not carry, a reading that is simply
# absent, or an entry that is not a condition at all are all FALSE — a malformed entry is
# quarantined as one that can never be met, never dropped, because dropping it would read as "no
# conditions" and let a typo make the rule LOUDER. A condition can therefore only ever make a rule
# quieter — it can never fire on data that is not there. An empty list is "no conditions", so every
# rule written before this existed evaluates exactly as it always did.

#: Comparisons for a numeric reading. ``in``/``not_in`` take a list (or "1,2,3") of numbers.
NUM_OPS: tuple[str, ...] = (">", ">=", "<", "<=", "==", "!=", "in", "not_in")

#: Comparisons for a text reading (a side, a state, a session name).
TEXT_OPS: tuple[str, ...] = ("==", "!=", "in", "not_in")

#: How several conditions combine. Unknown values read as ``"all"`` — the strict one.
MATCH_MODES: tuple[str, ...] = ("all", "any")


def _event_get(event: Any, key: str, default: Any = None) -> Any:
    """One field of an event, whether it arrived as a dict or as a small object."""
    if isinstance(event, dict):
        return event.get(key, default)
    return getattr(event, key, default)


def _ctx_get(ctx: Any, key: str, default: Any = None) -> Any:
    return ctx.get(key, default) if isinstance(ctx, dict) else default


def _first_num(*values: Any) -> Optional[float]:
    """The first value that is a usable number — the order is the caller's priority."""
    for value in values:
        out = _num(value, None)
        if out is not None:
            return out
    return None


def _first_text(*values: Any) -> Optional[str]:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _minutes_of_day(stamp_ms: Any) -> Optional[float]:
    """Minutes since local midnight for a timestamp — what a time-of-day condition compares against."""
    ms = _num(stamp_ms, None)
    if not ms or ms <= 0:
        return None
    local = time.localtime(ms / 1000)
    return float(local.tm_hour * 60 + local.tm_min)


def _side_of(event: Any) -> Optional[str]:
    return _first_text(_event_get(event, "side"), _event_get(event, "direction"),
                       _event_get(event, "aggressor"))


def _field_num(event: Any, ctx: Any, params: dict[str, Any]) -> Optional[float]:
    field = str(params.get("field") or "").strip()
    if not field:
        return None
    return _first_num(_event_get(event, field), _ctx_get(ctx, field))


def _field_text(event: Any, ctx: Any, params: dict[str, Any]) -> Optional[str]:
    field = str(params.get("field") or "").strip()
    if not field:
        return None
    return _first_text(_event_get(event, field), _ctx_get(ctx, field))


def _ctx_num(event: Any, ctx: Any, params: dict[str, Any]) -> Optional[float]:
    field = str(params.get("field") or "").strip()
    if not field:
        return None
    return _first_num(_ctx_get(ctx, field))


#: The condition catalogue: every reading a condition may compare, where it comes from, and whether
#: it compares as a number or as text. `read` is the one resolver; it returns None when the data is
#: simply not there, and the caller treats that as "false", never as zero.
CONDITION_KINDS: dict[str, dict[str, Any]] = {
    "price": {
        "label": "Price", "unit": "", "value": "number", "source": "event",
        "hint": "the event's own price, else the snapshot's last price",
        "read": lambda event, ctx, params: _first_num(
            _event_get(event, "price"), _event_get(event, "level"),
            _event_get(event, "px"), _ctx_get(ctx, "last_price")),
    },
    "delta": {
        "label": "Cumulative delta", "unit": "", "value": "number", "source": "either",
        "hint": "the snapshot's delta over its window, else a delta the event itself carries",
        "read": lambda event, ctx, params: _first_num(
            _delta_value(_ctx_get(ctx, "delta")), _event_get(event, "delta")),
    },
    "volume": {
        "label": "Volume", "unit": "", "value": "number", "source": "either",
        "hint": "the event's traded volume, else the snapshot's volume over the window",
        "read": lambda event, ctx, params: _first_num(
            _event_get(event, "volume"), _event_get(event, "total_volume"), _ctx_get(ctx, "volume")),
    },
    "size": {
        "label": "Size", "unit": "", "value": "number", "source": "event",
        "hint": "the size of the print the event is about",
        "read": lambda event, ctx, params: _first_num(_event_get(event, "size")),
    },
    "multiple": {
        "label": "Multiple of threshold", "unit": "x", "value": "number", "source": "event",
        "hint": "how many times the venue's big-trade threshold the print was",
        "read": lambda event, ctx, params: _first_num(
            _event_get(event, "multiple"), _event_get(event, "size_multiple")),
    },
    "levels": {
        "label": "Levels", "unit": "", "value": "number", "source": "event",
        "hint": "how many price levels the event covered (a sweep, a stacked imbalance)",
        "read": lambda event, ctx, params: _first_num(_event_get(event, "levels")),
    },
    "ticks": {
        "label": "Ticks moved", "unit": "t", "value": "number", "source": "event",
        "hint": "the distance the event moved — ticks moved, or the distance a level sat away",
        "read": lambda event, ctx, params: _first_num(
            _event_get(event, "ticks_moved"), _event_get(event, "ticks"),
            _event_get(event, "distance_ticks"), _event_get(event, "beyond_ticks")),
    },
    "zscore": {
        "label": "Speed z-score", "unit": "z", "value": "number", "source": "event",
        "hint": "how far the tape's speed stood out from its own normal",
        "read": lambda event, ctx, params: _first_num(_event_get(event, "zscore")),
    },
    "strength": {
        "label": "Divergence strength", "unit": "", "value": "number", "source": "event",
        "hint": "how strong a CVD divergence read",
        "read": lambda event, ctx, params: _first_num(_event_get(event, "strength")),
    },
    "pct": {
        "label": "Book pressure", "unit": "%", "value": "number", "source": "event",
        "hint": "one side's weight against its own normal, in percent",
        "read": lambda event, ctx, params: _first_num(
            _event_get(event, "pct"), _event_get(event, "ratio_pct")),
    },
    "share": {
        "label": "Share of resting size", "unit": "", "value": "number", "source": "event",
        "hint": "how much of a level's resting size a print took, or a refill replaced (0–1)",
        "read": lambda event, ctx, params: _first_num(_event_get(event, "share")),
    },
    "tape_speed": {
        "label": "Tape speed", "unit": "/s", "value": "number", "source": "ctx",
        "hint": "prints per second over the snapshot's window",
        "read": lambda event, ctx, params: _first_num(
            _ctx_get(ctx, "tape_speed"), _tape_speed_of(_ctx_get(ctx, "prints"),
                                                       _window_of(ctx, params))),
    },
    "spread_ticks": {
        "label": "Spread", "unit": "t", "value": "number", "source": "ctx",
        "hint": "the snapshot's spread in ticks",
        "read": lambda event, ctx, params: _first_num(_ctx_get(ctx, "spread_ticks")),
    },
    "session": {
        "label": "Session", "unit": "", "value": "text", "source": "ctx",
        "hint": "the session name the snapshot carries (london, us, asia) — use in to list several",
        "read": lambda event, ctx, params: _first_text(_session_name(_ctx_get(ctx, "session"))),
    },
    "side": {
        "label": "Side", "unit": "", "value": "text", "source": "event",
        "hint": "the aggressive side: buy or sell (bid/ask are read as the same thing)",
        "read": lambda event, ctx, params: _first_text(_side_of(event)),
    },
    "event_kind": {
        "label": "Event kind", "unit": "", "value": "text", "source": "event",
        "hint": "the event's own kind field — a CVD divergence's direction, for example",
        "read": lambda event, ctx, params: _first_text(_event_get(event, "kind")),
    },
    "state": {
        "label": "State", "unit": "", "value": "text", "source": "event",
        "hint": "the event's state (a radar level's defended / confirmed / spent / failed)",
        "read": lambda event, ctx, params: _first_text(_event_get(event, "state")),
    },
    "time": {
        "label": "Time of day", "unit": "min", "value": "number", "source": "either",
        "hint": "minutes since local midnight for the event's stamp (09:30 = 570)",
        "read": lambda event, ctx, params: _first_num(
            _minutes_of_day(_event_get(event, "ts_ms")), _minutes_of_day(_ctx_get(ctx, "now_ms"))),
    },
    "field": {
        "label": "Event field", "unit": "", "value": "number", "source": "event",
        "hint": "any numeric field of the event by name (params.field) — for one this catalogue "
                "does not name yet",
        "read": _field_num,
    },
    "ctx_field": {
        "label": "Snapshot field", "unit": "", "value": "number", "source": "ctx",
        "hint": "any numeric field of the snapshot by name (params.field)",
        "read": _ctx_num,
    },
    "text_field": {
        "label": "Event text field", "unit": "", "value": "text", "source": "event",
        "hint": "any text field of the event by name (params.field)",
        "read": _field_text,
    },
}


def condition_kinds() -> list[dict[str, Any]]:
    """The catalogue as the UI consumes it: no callables, and each kind's own list of legal ops."""
    out: list[dict[str, Any]] = []
    for name, spec in CONDITION_KINDS.items():
        value_class = str(spec["value"])
        out.append({
            "kind": name, "label": spec["label"], "unit": spec["unit"],
            "value": value_class, "source": spec["source"], "hint": spec["hint"],
            "ops": list(NUM_OPS if value_class == "number" else TEXT_OPS),
        })
    return out


def _delta_value(delta: Any) -> Optional[float]:
    """A snapshot's delta in either shape: the number itself, or the dict ``window_delta`` returns.

    A window that held no prints has no delta — its zero is the absence of a reading, not a measured
    balance — so a condition over it reads as unreadable and never meets (the malformed-reading rule).
    A shape that does not say how many prints it summed is taken at its word.
    """
    if isinstance(delta, dict):
        prints = _num(delta.get("prints"), None)
        if prints is not None and prints <= 0:
            return None
        return _num(delta.get("value"), None)
    return _num(delta, None)


def _session_name(session: Any) -> Optional[str]:
    if isinstance(session, dict):
        return _first_text(session.get("name"), session.get("session"), session.get("state"))
    return _first_text(session)


def _window_of(ctx: Any, params: dict[str, Any]) -> int:
    """The window a computed snapshot reading is measured over: the condition's own, or the snapshot's."""
    own = _num(params.get("window_ms"), None)
    if own and own > 0:
        return int(own)
    theirs = _num(_ctx_get(ctx, "window_ms"), None)
    return int(theirs) if theirs and theirs > 0 else 60_000


def _as_list(value: Any) -> list[Any]:
    """A condition's value as a list: lists stay, "a,b" splits, one value becomes a one-item list."""
    if isinstance(value, (list, tuple, set)):
        return [v for v in value]
    if isinstance(value, str):
        sep = "," if "," in value else "|" if "|" in value else ""
        return [part.strip() for part in value.split(sep)] if sep else [value.strip()]
    return [] if value is None else [value]


def _compare(op: str, value: Any, expected: Any, value_class: str) -> bool:
    """One comparison. False for an op that does not belong, or an expected value that is not one."""
    if value_class == "number":
        if op not in NUM_OPS:
            return False
        left = _num(value, None)
        if left is None:
            return False
        if op in ("in", "not_in"):
            items = [_num(item, None) for item in _as_list(expected)]
            hit = any(item is not None and item == left for item in items)
            return hit if op == "in" else (not hit and any(item is not None for item in items))
        right = _num(expected, None)
        if right is None:
            return False
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        return left == right if op == "==" else left != right
    if op not in TEXT_OPS:
        return False
    left_text = str(value).strip().lower()
    if op in ("in", "not_in"):
        # The same reading the ==/!= branch below uses: a side arrives as bid/ask or buy/sell
        # depending on the detector, so an author's list may say either — compared as raw strings,
        # `in ["ask"]` never met on a detector that says "sell", while `== ask` did, and
        # `not_in ["bid"]` fired on the buys it meant to exclude.
        items = [_side_word(str(item).strip().lower()) for item in _as_list(expected)]
        hit = _side_word(left_text) in items
        return hit if op == "in" else (not hit and bool(items))
    right_text = _first_text(expected)
    if right_text is None:
        return False
    # A side arrives as bid/ask or buy/sell depending on the detector; both mean the same trade.
    left_text, right_text = _side_word(left_text), _side_word(right_text.lower())
    return left_text == right_text if op == "==" else left_text != right_text


def _side_word(text: str) -> str:
    """bid/ask and buy/sell are the same two sides, said by different detectors."""
    word = str(text or "").strip().lower()
    if word in ("bid", "buy", "b"):
        return "buy"
    if word in ("ask", "sell", "s"):
        return "sell"
    return word


def _tape_speed_of(prints: Any, window_ms: int, end_ms: int | None = None) -> Optional[float]:
    """Prints per second over the span the prints actually cover.

    §148 (own finding, from AB-04's receipt): the provider's tape is a fixed ring (240 prints), so
    a "60 s" window is regularly a fraction of a minute — the old division by the window
    under-claimed a 240-print burst as 4 per second. The rate is measured over the covered span
    (never wider than the window itself); fewer than two stamps has no span to divide by.
    When ``end_ms`` is given the span is ``end_ms - oldest`` (the same covered span the labels use);
    otherwise it is the prints' own first-to-last span.
    """
    rows = [row for row in (prints or []) if isinstance(row, dict)]
    stamps = sorted(s for s in (_num(row.get("ts_ms"), None) for row in rows) if s and s > 0)
    if len(stamps) < 2 or window_ms <= 0:
        return None
    if end_ms is not None:
        span_ms = min(float(window_ms), float(end_ms - stamps[0]))
    else:
        span_ms = min(float(window_ms), float(stamps[-1] - stamps[0]))
    span_ms = span_ms or float(window_ms)
    return round(len(stamps) / (span_ms / 1000.0), 2)


def match_of(rule: Any) -> str:
    """How a rule's conditions combine. Anything but a known mode reads as the strict one."""
    if isinstance(rule, dict):
        raw = rule.get("match")
    else:
        raw = getattr(rule, "match", None)
    text = str(raw if raw is not None else "").strip().lower()
    return text if text in MATCH_MODES else "all"


def _unreadable_entry(entry: Any) -> dict[str, Any]:
    """A never-met stand-in for a ``conditions`` entry that is not a condition.

    Dropping such an entry would leave the rule firing on its kind and thresholds alone — LOUDER
    than the author wrote it, and the opposite of this section's own rule that a condition may only
    ever make a rule quieter. The stand-in keeps the authored entry under ``entry`` (so a save
    round-trips the author's own text instead of erasing it) and names what it is under
    ``unreadable``, which the rehearsal's per-condition words quote back.
    """
    if entry is None:
        what = "null"
    elif isinstance(entry, bool):
        what = "true/false"
    elif isinstance(entry, str):
        what = "a string"
    elif isinstance(entry, (int, float)):
        what = "a number"
    elif isinstance(entry, (list, tuple)):
        what = "a list"
    else:
        what = "not a plain value"
    return {"kind": "", "op": "", "value": None, "params": {}, "unreadable": what, "entry": entry}


def conditions_of(rule: Any) -> list[dict[str, Any]]:
    """A rule's conditions, as plain dicts, capped at ``MAX_CONDITIONS``.

    Every entry the author wrote is kept: an entry that is not an object is quarantined as a
    condition that can never be met (see ``_unreadable_entry``), and a single condition object not
    wrapped in a list is read as the one condition it says it is. A missing value (``None``) is
    "no conditions", which is what keeps every rule written before conditions existed unchanged.
    """
    if isinstance(rule, dict):
        raw = rule.get("conditions")
    else:
        raw = getattr(rule, "conditions", None)
    if raw is None:
        return []
    if isinstance(raw, dict):
        raw = [raw]      # a single condition object is read as the one condition it is
    elif not isinstance(raw, (list, tuple)):
        raw = [raw]      # an unreadable value quarantines the rule rather than freeing it
    out: list[dict[str, Any]] = []
    for item in raw:
        out.append(item if isinstance(item, dict) else _unreadable_entry(item))
        if len(out) >= MAX_CONDITIONS:
            break
    return out


def _effective_conditions(rule: Any, settings: Any = None) -> list[dict[str, Any]]:
    """The conditions actually evaluated: the rule's list, capped by the settings block.

    A ``max_conditions`` of 0 means the engine ignores conditions entirely (every rule then reads as
    condition-free), which is the off switch a user reaches for when a set of rules is behaving
    oddly — it can never make a rule fire *more* than its kind and params alone.
    """
    conds = conditions_of(rule)
    if not isinstance(settings, dict):
        return conds
    cap = _int_in(settings.get("max_conditions"), DEFAULTS["max_conditions"], 0, MAX_CONDITIONS)
    return conds[:cap]


#: What a rule's cooldown counts: the rule itself (the original behaviour) or each instrument.
COOLDOWN_SCOPES: tuple[str, ...] = ("rule", "symbol")


def _fire_key(rule_id: str, symbol: str, scope: str) -> str:
    """The cooldown clock a rule reads: one per rule, or one per rule and instrument."""
    return f"{rule_id}|{symbol}" if str(scope).strip().lower() == "symbol" else str(rule_id)

#: The overrides a rule's own ``context`` block may carry. Short keys because they sit inside the
#: rule; the module settings spell the same things with a ``context_`` prefix.
RULE_CONTEXT_KEYS: tuple[str, ...] = (
    "enabled", "format", "max_chars", "prints", "levels", "window_ms", "channels")


def rule_context(raw: Any) -> Optional[dict[str, Any]]:
    """A rule's own evidence-block request: None when the rule did not ask for one.

    The presence of the key is the opt-in, so an empty dict means "yes, with the module's defaults"
    and ``False`` means "no". A dict is trimmed to the keys the block understands.
    """
    if raw is None or raw is False:
        return None
    if raw is True:
        return {}
    if isinstance(raw, dict):
        return {key: raw[key] for key in RULE_CONTEXT_KEYS if key in raw}
    if isinstance(raw, str):
        return None if raw.strip().lower() in ("", "0", "false", "no", "off") else {}
    if isinstance(raw, (int, float)):
        return None if not raw else {}
    return None


def evaluate_condition(condition: Any, event: Any = None, ctx: Any = None) -> bool:
    """One condition against one event and the snapshot. False for anything it cannot read."""
    if not isinstance(condition, dict):
        return False
    spec = CONDITION_KINDS.get(str(condition.get("kind") or "").strip().lower())
    if spec is None:
        return False
    op = str(condition.get("op") or "").strip()
    params = condition.get("params") if isinstance(condition.get("params"), dict) else {}
    try:
        value = spec["read"](event, ctx, params)
    except Exception:                        # a resolver may meet anything; a rule must not raise
        return False
    if value is None:
        return False
    try:
        return _compare(op, value, condition.get("value"), str(spec["value"]))
    except Exception:
        return False


def evaluate_conditions(rule: Any, event: Any = None, ctx: Any = None,
                        settings: Any = None) -> bool:
    """The rule's conditions against the event, combined by its ``match``.

    No conditions means yes — that is what keeps every rule written before this existed unchanged.
    """
    conds = _effective_conditions(rule, settings)
    if not conds:
        return True
    results = [evaluate_condition(condition, event, ctx) for condition in conds]
    return any(results) if match_of(rule) == "any" else all(results)


def _conditions_detail(rule: Any, met: bool) -> str:
    """The conditions gate's sentence in the rule's own terms.

    ``all`` requires every condition, so a failure reports one unmet; ``any`` requires just one, so
    a failure says none is met — reporting a single unmet one would read as if the bar were every —
    and a pass says at least one, never every (only one may have met).
    """
    if match_of(rule) == "any":
        return "at least one condition is met" if met else "no condition is met"
    return "every condition is met" if met else "at least one condition is not met"


def condition_results(rule: Any, event: Any = None, ctx: Any = None,
                      settings: Any = None) -> list[dict[str, Any]]:
    """Per-condition detail, in words, for the builder's Test fire — never raises."""
    out: list[dict[str, Any]] = []
    for condition in _effective_conditions(rule, settings):
        kind = str((condition or {}).get("kind") or "").strip().lower()
        params = condition.get("params") if isinstance(condition.get("params"), dict) else {}
        spec = CONDITION_KINDS.get(kind)
        row: dict[str, Any] = {
            "kind": kind, "op": str(condition.get("op") or ""), "value": condition.get("value"),
            "params": dict(params), "met": False, "read": None, "why": "",
            "label": str(spec["label"]) if spec else kind,
        }
        if condition.get("unreadable"):
            row["label"] = "not a condition"
            row["why"] = f"this entry is {condition['unreadable']}, not a condition — it can never be met"
        elif spec is None:
            row["why"] = f"no condition called '{kind}' — this one can never be met"
        else:
            try:
                read = spec["read"](event, ctx, params)
            except Exception:
                read = None
            row["read"] = read
            if read is None:
                row["why"] = f"the event and the snapshot carry no {spec['label'].lower()} reading"
            elif str(condition.get("op") or "").strip() not in (
                    NUM_OPS if str(spec["value"]) == "number" else TEXT_OPS):
                row["why"] = f"'{row['op']}' is not a comparison this reading understands"
            else:
                row["met"] = evaluate_condition(condition, event, ctx)
                row["why"] = "" if row["met"] else "read but did not match"
        out.append(row)
    return out


@dataclass
class AlertRule:
    id: str
    name: str
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    cooldown_s: float = 30.0
    channels: list[str] = field(default_factory=lambda: ["ui"])
    fired: int = 0
    last_fired_ms: int = 0
    #: Extra readings the rule requires, combined by ``match`` (see ``evaluate_conditions``).
    conditions: list[dict[str, Any]] = field(default_factory=list)
    match: str = "all"
    #: The rule's request for an evidence block: None = no block, {} = the module's defaults,
    #: or overrides from ``RULE_CONTEXT_KEYS``.
    context: Optional[dict[str, Any]] = None
    #: ``"rule"`` (one cooldown for the whole rule, the original behaviour) or ``"symbol"``
    #: (each instrument gets its own cooldown, so a busy symbol cannot mute a quiet one).
    cooldown_scope: str = "rule"
    #: At most ``max_per_window`` fires inside each aligned window of this many seconds (0 = off).
    once_per_window_s: float = 0.0
    max_per_window: int = 1

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AlertRule":
        if not isinstance(raw, dict):
            # Nothing readable to build a rule from. A disabled placeholder beats a raise (which
            # would take the whole rules load down at boot) and beats an enabled default (which
            # would fire on everything) — and the builder shows a person what to delete.
            logger.debug("alert rule: unreadable entry %r — kept disabled", raw)
            raw = {"enabled": False, "name": str(raw)[:60] or "unreadable rule"}
        raw = raw or {}
        return cls(
            id=str(raw.get("id") or f"rule-{int(time.time()*1000)}"),
            name=str(raw.get("name") or raw.get("kind", "rule")),
            kind=str(raw.get("kind", "big_trade")),
            params=_rule_params(raw.get("params")),
            enabled=_rule_enabled(raw),
            cooldown_s=max(0.0, _num(raw.get("cooldown_s"), 30.0)),
            channels=_rule_channels(raw.get("channels")),
            conditions=[dict(condition) for condition in conditions_of(raw)],
            match=match_of(raw),
            context=rule_context(raw.get("context")),
            cooldown_scope=str(raw.get("cooldown_scope") or "rule").strip().lower()
            if str(raw.get("cooldown_scope") or "rule").strip().lower() in COOLDOWN_SCOPES else "rule",
            once_per_window_s=max(0.0, float(_num(raw.get("once_per_window_s"), 0.0) or 0.0)),
            max_per_window=max(1, int(_num(raw.get("max_per_window"), 1) or 1)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "kind": self.kind, "params": self.params,
                "enabled": self.enabled, "cooldown_s": self.cooldown_s, "channels": self.channels,
                "fired": self.fired, "last_fired_ms": self.last_fired_ms,
                "conditions": [dict(condition) for condition in self.conditions],
                "match": self.match, "context": dict(self.context) if self.context is not None else None,
                "cooldown_scope": self.cooldown_scope,
                "once_per_window_s": self.once_per_window_s,
                "max_per_window": self.max_per_window}


@dataclass
class Alert:
    rule_id: str
    name: str
    kind: str
    symbol: str
    ts_ms: int
    message: str
    severity: str = "info"          # info | warning | critical
    data: dict[str, Any] = field(default_factory=dict)
    channels: list[str] = field(default_factory=lambda: ["ui"])
    #: The evidence block the rule asked for ("" when it did not): what fired, with the window's
    #: delta, the biggest prints and the nearest walls — carried by every channel.
    context: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"rule_id": self.rule_id, "name": self.name, "kind": self.kind, "symbol": self.symbol,
                "ts_ms": self.ts_ms, "message": self.message, "severity": self.severity,
                "data": self.data, "channels": list(self.channels), "context": self.context}


# ══════════════════════════════════════════════════════════════
# The evidence block — what fired, attached to the notification
# ══════════════════════════════════════════════════════════════
#
# A notification that says "sweep on BTCUSDT" is a prompt to go and look. The block is what a channel
# that has to stand on its own can carry: the trigger, the window's delta, the biggest prints, the
# nearest resting levels and the session state, in six short lines or a few CSV rows, hard-capped.
#
# The block reads two things and invents nothing:
#
# * ``event`` — the detection payload that fired the rule (always there);
# * ``ctx``   — an optional snapshot the engine holds (``ContextBuffer``, or a hub adapter). Its
#   whole contract:
#
#       now_ms        int    the snapshot's stamp (the event's own stamp wins)
#       last_price    float
#       spread_ticks  float
#       window_ms     int    the window ``delta``/``tape_speed`` refer to
#       delta         float | {"value": .., "buy": .., "sell": ..} | missing
#       tape_speed    float  prints per second, when the provider already knows it
#       prints        [{"ts_ms": .., "price": .., "size": .., "side": "buy"|"sell"}]  newest last
#       levels        [{"price": .., "size": .., "side": "bid"|"ask", "distance_ticks": ..}]
#       session       {"name": "us", "state": "open", "minutes_in": 90, "vwap": .., "range_low": ..,
#                      "range_high": ..}  (or just a name)
#
# Delta, tape speed and the biggest prints are computed from ``prints`` when the provider did not
# pre-compute them, so wiring a snapshot up costs one call per tick and nothing else.

#: A print's side, normalised: the detectors say buy/sell, the book says bid/ask, and a print whose
#: side nobody knows contributes to nothing.
def _print_side(side: Any) -> str:
    word = _side_word(str(side if side is not None else ""))
    return word if word in ("buy", "sell") else ""


def _print_rows(prints: Any) -> list[dict[str, Any]]:
    """Whatever the provider handed us, as clean print dicts with a usable stamp."""
    rows: list[dict[str, Any]] = []
    for row in (prints if isinstance(prints, (list, tuple, deque)) else []):
        if not isinstance(row, dict):
            continue
        stamp = _num(row.get("ts_ms", row.get("ts")), None)
        if stamp and stamp > 0 and stamp < 10_000_000_000:      # seconds arrived despite the name
            stamp *= 1000
        price = _num(row.get("price"), None)
        if not stamp or price is None:
            continue
        rows.append({"ts_ms": int(stamp), "price": price,
                     "size": _num(row.get("size"), 0.0) or 0.0, "side": _print_side(row.get("side"))})
    rows.sort(key=lambda r: r["ts_ms"])
    return rows


def _windowed(prints: Any, window_ms: int, end_ms: Optional[int] = None) -> tuple[list[dict[str, Any]], int]:
    """The prints inside the window that ends at ``end_ms`` (or at the newest print).

    Both bounds, always. A snapshot held NOW, read against an older event, holds prints that came
    after it — the window ended before them, so they are not inside it, however close they look.
    """
    rows = _print_rows(prints)
    end = int(end_ms) if end_ms else (rows[-1]["ts_ms"] if rows else 0)
    if not end:
        return [], 0
    span = max(0, int(window_ms))
    return [row for row in rows if end - span < row["ts_ms"] <= end], end


def _covered_span(prints: Any, window_ms: int, end_ms: int) -> int:
    """How much of the window the tape ring can vouch for (§148 own finding).

    The provider hands over a fixed ring (240 prints), so a "60 s" window is regularly a fraction
    of a minute. When the ring's oldest print lands inside the window, the measurable span is
    ``end - oldest``; when the ring reaches past the window's start, the window itself is the
    span — the quiet before the ring's first print is data, not a missing window.
    """
    rows = [row for row in (prints or []) if isinstance(row, dict)]
    stamps = sorted(s for s in (_num(row.get("ts_ms"), None) for row in rows) if s and s > 0)
    want = max(0, int(window_ms))
    if not stamps or not end_ms:
        return want
    if stamps[0] <= int(end_ms) - want:
        return want
    return max(0, min(want, int(end_ms) - int(stamps[0])))


def window_delta(prints: Any, window_ms: int = 60_000, end_ms: Optional[int] = None) -> dict[str, Any]:
    """Cumulative delta over the window: buy aggressor volume minus sell aggressor volume.

    A print whose side is unknown counts toward neither, and is reported separately — a delta built
    on half a tape has to be readable as such rather than quietly halved.
    """
    rows, end = _windowed(prints, window_ms, end_ms)
    buy = sum(row["size"] for row in rows if row["side"] == "buy")
    sell = sum(row["size"] for row in rows if row["side"] == "sell")
    known = buy + sell
    return {"window_ms": int(window_ms), "end_ms": end, "prints": len(rows),
            "buy": round(buy, 6), "sell": round(sell, 6), "value": round(buy - sell, 6),
            "unknown": len([row for row in rows if not row["side"]]),
            "buy_pct": round(buy / known * 100, 0) if known else 0.0,
            "sell_pct": round(sell / known * 100, 0) if known else 0.0}


def biggest_prints(prints: Any, count: int = 3, window_ms: int = 60_000,
                   end_ms: Optional[int] = None) -> list[dict[str, Any]]:
    """The window's biggest prints by size, returned in time order (the tape reads left to right)."""
    rows, _end = _windowed(prints, window_ms, end_ms)
    top = sorted(rows, key=lambda row: -row["size"])[:max(0, int(count))]
    return sorted(top, key=lambda row: row["ts_ms"])


def _level_side(side: Any) -> str:
    """A resting level's side keeps the book's own word — bid/ask, not buy/sell (nothing aggressed)."""
    word = str(side if side is not None else "").strip().lower()
    return {"b": "bid", "buy": "bid", "bid": "bid", "s": "ask", "sell": "ask", "ask": "ask"}.get(word, word)


def nearest_levels(levels: Any, ref_price: Any = None, count: int = 3) -> list[dict[str, Any]]:
    """The levels nearest the reference price, nearest first — or by distance when there is none."""
    rows = [row for row in (levels if isinstance(levels, (list, tuple)) else []) if isinstance(row, dict)]
    ref = _num(ref_price, None)
    out: list[dict[str, Any]] = []
    for row in rows:
        price = _num(row.get("price"), None)
        if price is None:
            continue
        distance = _num(row.get("distance_ticks"), None)
        if distance is None and ref is not None:
            distance = abs(price - ref)
        out.append({"price": price, "size": _num(row.get("size", row.get("volume")), 0.0) or 0.0,
                    "side": _level_side(row.get("side")),
                    "distance_ticks": distance if distance is not None else float("inf")})
    out.sort(key=lambda row: row["distance_ticks"])
    return out[:max(0, int(count))]


def _fmt_price(value: Any) -> str:
    """Prices span a 77 000 index and a 0.0001-grid instrument, so the precision follows the size."""
    out = _num(value, None)
    if out is None:
        return ""
    a = abs(out)
    if a == 0:
        return "0"
    if a >= 1:
        return f"{out:,.2f}"
    if a >= 0.01:
        return f"{out:.4f}"
    return f"{out:.6g}"


def _fmt_size(value: Any) -> str:
    out = _num(value, None)
    if out is None:
        return ""
    a = abs(out)
    if a >= 1000:
        return f"{out / 1000:.2f}K"
    if a >= 1:
        return f"{out:.2f}"
    if a >= 0.01:
        return f"{out:.3f}"
    return f"{out:.2g}"


def _fmt_num(value: Any) -> str:
    """A number with the arithmetic noise taken off — ``0.5000000000109139`` prints as ``0.5``.

    The tape is full of prices and sizes that went through tick arithmetic, and their float error
    rides straight into an alert's text when the value is interpolated raw (measured live:
    "1.240000000000009 pulled from the bid 0.5000000000109139 ticks from mid"). Six decimals, then
    trailing zeros trimmed; anything that rounds to nothing falls back to ``%g`` so it is never lost.
    """
    out = _num(value, None)
    if out is None:
        return ""
    text = f"{out:.6f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-") else f"{out:g}"


#: How the trigger line reads the event's own fields: the field, the word in front of it, and a unit
#: that rides the value. Anything not listed prints as ``name value`` — never dropped.
_TRIGGER_FIELDS: dict[str, tuple[str, ...]] = {
    "big_trade": ("side", "size", "price", "multiple"),
    "block_trade": ("side", "size", "price", "multiple"),
    "sweep": ("side", "levels", "size", "price", "duration_ms"),
    "stop_run": ("direction", "ticks_moved", "duration_ms", "volume"),
    "iceberg": ("side", "fills", "price", "modal_size"),
    "speed_spike": ("zscore", "volume_5s", "trades_5s"),
    "cvd_divergence": ("kind", "strength", "note"),
    "heat_pull": ("side", "size", "price"),
    "heat_stack": ("side", "size", "price"),
    "wall": ("side", "size", "price"),
    "wall_age": ("price", "size", "held_ms", "detail"),
    "stacked_imbalance": ("side", "levels", "volume", "from_price", "to_price"),
    "intent_pressure": ("side", "pct", "threshold"),
    "pulled_size": ("side", "size", "price", "distance_ticks"),
    "trapped_traders": ("side", "level", "beyond_ticks", "reclaim_ms"),
    "vwap_cross": ("side", "ticks", "vwap"),
    "depth_execution": ("side", "size", "share", "price"),
    "depth_refill": ("price", "size", "share", "refill_ms"),
    "unfinished_business": ("side", "price", "arms"),
    "node_zone": ("price", "count", "volume"),
    "level_touch": ("price", "last", "at_tol"),
    "radar_level": ("state", "source", "price", "touches"),
    "liquidation": ("side", "size", "price"),
}

#: The fallback for a kind with no row above (a detector added later): read like a print.
_DEFAULT_TRIGGER_FIELDS: tuple[str, ...] = ("side", "size", "price", "levels", "ticks_moved", "volume")

#: field -> (word in front, unit). The unit decides how the number prints: n = a count, s = a size,
#: p = a price, t = ticks, ms = a duration, x/z/% as they read. "text" is a word, not a number.
_TRIGGER_WORDS: dict[str, tuple[str, str]] = {
    "side": ("", "text"), "direction": ("", "text"), "kind": ("", "text"), "state": ("", "text"),
    "source": ("", "text"), "detail": ("", "text"), "note": ("note:", "text"),
    "price": ("@", "p"), "level": ("@", "p"), "last": ("@", "p"), "vwap": ("vwap", "p"),
    "from_price": ("from", "p"), "to_price": ("to", "p"),
    "size": ("size", "s"), "modal_size": ("modal", "s"), "volume": ("vol", "s"),
    "volume_5s": ("vol5s", "s"), "strength": ("strength", "s"),
    "levels": ("levels", "n"), "fills": ("fills", "n"), "arms": ("arms", "n"), "count": ("bars", "n"),
    "touches": ("tests", "n"), "trades_5s": ("trades5s", "n"),
    "threshold": ("thr", "%"), "pct": ("", "%"), "share": ("", "%"),
    "multiple": ("", "x"), "zscore": ("z", "z"), "ticks": ("", "t"), "ticks_moved": ("", "t"),
    "distance_ticks": ("", "t"), "beyond_ticks": ("", "t"), "at_tol": ("±", "s"),
    "duration_ms": ("", "ms"), "held_ms": ("", "ms"), "reclaim_ms": ("", "ms"), "refill_ms": ("", "ms"),
}


def _trigger_words(field: str, raw: Any) -> Optional[str]:
    """One event field as a word or two, or None when the event does not carry it."""
    before, unit = _TRIGGER_WORDS.get(field, (field.replace("_", " "), "s"))
    if field in ("side", "direction"):
        text = _print_side(raw)
        return text.upper() if text else None
    if unit == "text":
        text = _first_text(raw)
        return (f"{before} {text}" if before else text) if text else None
    number = _num(raw, None)
    if number is None:
        return None
    if unit == "%":
        # A share arrives as 0..1; a percentage is what a reader can compare against the threshold.
        shown = f"{number * 100.0 if field == 'share' else number:.0f}%"
    elif unit == "x":
        shown = f"{number:.2f}x"
    elif unit == "z":
        shown = f"{number:.2f}z"
    elif unit == "t":
        shown = f"{number:.2f}t"
    elif unit == "ms":
        shown = f"{number:.0f}ms" if number < 10_000 else f"{number / 1000:.1f}s"
    elif unit == "n":
        shown = f"{number:.0f}"
    elif unit == "p":
        return f"{before}{_fmt_price(number)}" if before else _fmt_price(number)
    else:
        shown = _fmt_size(number)
    return f"{before} {shown}" if before else shown


def _trigger_line(event: Any, ctx: Any, kind: str) -> str:
    """``sweep — SELL · levels 7 · size 42.50 · @63120.50 · 380ms``: the event, in its own numbers."""
    name = str(kind or _first_text(_event_get(event, "kind")) or "event").strip()
    keys = _TRIGGER_FIELDS.get(name, _DEFAULT_TRIGGER_FIELDS)
    parts: list[str] = []
    for key in keys:
        try:
            word = _trigger_words(key, _event_get(event, key))
        except Exception:
            word = None
        if word:
            parts.append(word)
        if len(parts) >= 5:
            break
    return f"{name} — " + " · ".join(parts) if parts else name


def context_config(rule: Any = None, settings: Any = None) -> dict[str, Any]:
    """The evidence block's effective config: the module settings, then the rule's own overrides.

    ``enabled`` is False unless the rule opted in (a ``context`` key on the rule) *and* the module's
    master switch is on — so a rule written before this existed never grows a block.
    """
    base = clean(settings)
    out: dict[str, Any] = dict(base)
    out["context_channels"] = list(base["context_channels"])
    out["enabled"] = False
    request = rule.get("context") if isinstance(rule, dict) else getattr(rule, "context", None)
    # One definition of "did the rule ask for one?" — so a `context: false` that came back from a
    # form or a config file means no, exactly as `rule_context` reads it.
    asked = rule_context(request)
    if asked is None:
        return out
    out["enabled"] = bool(base["context_enabled"])
    if not asked:
        return out
    request = asked                      # trimmed to the keys the block understands
    if "enabled" in request:
        out["enabled"] = out["enabled"] and _bool(request.get("enabled"), True)
    if "format" in request:
        out["context_format"] = _text_in(request.get("format"), base["context_format"], CONTEXT_FORMATS)
    if "max_chars" in request:
        out["context_max_chars"] = _int_in(request.get("max_chars"), base["context_max_chars"], 40, 2_000)
    if "prints" in request:
        out["context_prints"] = _int_in(request.get("prints"), base["context_prints"], 0, 10)
    if "levels" in request:
        out["context_levels"] = _int_in(request.get("levels"), base["context_levels"], 0, 10)
    if "window_ms" in request:
        out["context_window_ms"] = _int_in(request.get("window_ms"), base["context_window_ms"],
                                           1_000, 3_600_000)
    if "channels" in request:
        out["context_channels"] = _channel_list(request.get("channels"))
    return out


def _cap_lines(lines: list[str], max_chars: int) -> str:
    """Whole lines only, then a ``+N more`` note. With rows to show it never returns nothing: when
    the note leaves no room for even one whole line, the first line rides cut and marked — an empty
    block reads as "the snapshot was empty", and that sentence must stay true."""
    rows = [str(line) for line in lines if str(line).strip()]
    cap = max(1, int(max_chars))
    if not rows:
        return ""
    out: list[str] = []
    used = 0
    for line in rows:
        cost = len(line) + (1 if out else 0)
        if used + cost > cap:
            break
        out.append(line)
        used += cost
    remaining = len(rows) - len(out)
    if remaining <= 0:
        return "\n".join(out)
    note = f"+{remaining} more"
    while out and used + len(note) + 2 > cap:
        used -= len(out.pop()) + 1
        remaining += 1
        note = f"+{remaining} more"
    if not out:
        # Nothing fit, or making room for the note emptied the block: cut the first line, marked —
        # the same honest form as a cap too small for even one line. Never a silent "".
        return (rows[0][:max(0, cap - 1)] + "…")[:cap]
    if out and used + len(note) + 2 <= cap:
        out.append(note)
    return "\n".join(out)[:cap]


def _cap_csv(lines: list[str], max_chars: int) -> str:
    """The CSV form's cap: whole rows, and the marker is a row of the same shape.

    A bare "+N more" line — or a row sliced mid-field — would leave the block unreadable to a
    spreadsheet, so the marker rides as its own three-field row (``note,cap,+N more rows``, short-
    ened only if the cap leaves no room for the long form) and no row is ever cut. The column
    header always rides, uncut: at the smallest legal cap (40) it is what keeps an empty answer
    from reading as "the snapshot was empty".
    """
    rows = [str(line) for line in lines if str(line).strip()]
    cap = max(1, int(max_chars))
    if len(rows) <= 1:
        return "\n".join(rows)
    out: list[str] = [rows[0]]
    used = len(rows[0])
    remaining = len(rows) - 1
    for line in rows[1:]:
        cost = len(line) + 1
        if used + cost > cap:
            break
        out.append(line)
        used += cost
        remaining -= 1
    if remaining <= 0:
        return "\n".join(out)
    while True:
        note = next((f"note,cap,+{remaining}{suffix}" for suffix in (" more rows", " more", "")
                     if used + 1 + len(f"note,cap,+{remaining}{suffix}") <= cap), "")
        if note or len(out) <= 1:
            break
        used -= len(out.pop()) + 1
        remaining += 1
    if note:
        out.append(note)
    return "\n".join(out)


def _block_sections(event: Any, ctx: Any, cfg: dict[str, Any], kind: str) -> list[tuple[str, str, str]]:
    """The block's readings as (section, key, value) — one source for both the text and the CSV form."""
    rows: list[tuple[str, str, str]] = []
    now_ms = _num(_event_get(event, "ts_ms"), None) or _num(_ctx_get(ctx, "now_ms"), None) or 0
    symbol = _first_text(_event_get(event, "symbol"), _ctx_get(ctx, "symbol")) or ""
    window_ms = int(cfg["context_window_ms"])
    prints = _ctx_get(ctx, "prints")
    window, end = _windowed(prints, window_ms, int(now_ms) or None)
    # §148 (own finding): "60 s" is often the window that was ASKED for, not the span the tape
    # covers — the ring is 240 prints, seconds long at book speed. Every span below is clamped to
    # what the ring can vouch for, so the labels say the span that was measured.
    covered = _covered_span(prints, window_ms, end)
    price = _first_num(_event_get(event, "price"), _event_get(event, "level"),
                       _ctx_get(ctx, "last_price")) 
    if price is None and window:
        price = window[-1]["price"]

    stamp = time.strftime("%H:%M:%S", time.localtime((int(now_ms) or end) / 1000)) if (now_ms or end) else ""
    head = " · ".join(part for part in (stamp, symbol.upper(), _fmt_price(price)) if part)
    rows.append(("head", "time", stamp))
    rows.append(("head", "symbol", symbol.upper()))
    rows.append(("head", "price", _fmt_price(price)))
    rows.append(("head", "line", head))
    rows.append(("trigger", "kind", str(kind or "")))
    rows.append(("trigger", "line", _trigger_line(event, ctx, kind)))

    delta = _ctx_get(ctx, "delta")
    if isinstance(delta, dict):
        ends_at = _num(delta.get("end_ms"), None)
        if ends_at is not None and (int(now_ms) or 0) and int(ends_at) > int(now_ms):
            # A snapshot held NOW, read against an older event: the provider's own delta ends after
            # the window this block describes, so it would smuggle the current tape into an old one.
            delta = None
    if not isinstance(delta, dict):
        delta = window_delta(prints, window_ms, (int(now_ms) or None)) if window else (
            {"value": _num(delta, None)} if delta is not None else None)
    if isinstance(delta, dict) and delta.get("value") is not None:
        value = _num(delta.get("value"), 0.0) or 0.0
        span = int(_num(delta.get("window_ms"), window_ms) or window_ms)
        short = 0 < covered < span                     # §148 own finding: the ring is the shorter span
        if short:
            span = covered
        counted = _num(delta.get("prints"), None)
        span_label = (f"delta {span / 1000:.0f}s" + (f" of {window_ms / 1000:.0f}s" if short else ""))
        if counted is not None and counted <= 0:
            # A window that held no prints has no delta: "+0.00" is a measured balance, and printing
            # it here would claim net-zero flow over a tape that never spoke. Name the emptiness.
            rows.append(("delta", "line", span_label + ": no prints"))
        else:
            detail = span_label + f": {value:+,.2f}"
            shares = ""
            if delta.get("buy_pct") is not None and delta.get("sell_pct") is not None and (
                    delta.get("buy") or delta.get("sell")):
                shares = f" (buy {float(delta['buy_pct']):.0f}% / sell {float(delta['sell_pct']):.0f}%)"
            rows.append(("delta", "seconds", f"{span / 1000:.0f}"))
            rows.append(("delta", "value", f"{value:+.2f}"))
            rows.append(("delta", "line", detail + shares))

    speed = _first_num(_ctx_get(ctx, "tape_speed"), None)
    if speed is None and window:
        speed = _tape_speed_of(prints, window_ms, end)
    spread = _num(_ctx_get(ctx, "spread_ticks"), None)
    extras = []
    short = 0 < covered < int(window_ms)               # the span the tape can vouch for, per section
    if speed is not None:
        # A rate is only printed for a span the tape holds: below one print a second, or when the
        # ring cannot reach the window's start, the count and the measured span are the honest form.
        if short:
            extras.append(f"tape {len(window)} prints in {max(1, round(covered / 1000))}s"
                          f" of {window_ms / 1000:.0f}s")
        elif speed >= 1 or not window:
            extras.append(f"tape {speed:.1f}/s")
        else:
            extras.append(f"tape {len(window)} prints in {window_ms / 1000:.0f}s")
        rows.append(("tape", "speed", f"{speed:.2f}"))
    elif window:
        # One print has no rate to state; the count and the span it was seen in still are measured.
        span_text = (f"{max(1, round(covered / 1000))}s of {window_ms / 1000:.0f}s" if short
                     else f"{window_ms / 1000:.0f}s")
        extras.append(f"tape {len(window)} print{'s' if len(window) != 1 else ''} in {span_text}")
    if spread is not None:
        extras.append(f"spread {spread:.1f}t")
        rows.append(("tape", "spread_ticks", f"{spread:.2f}"))
    if extras:
        rows.append(("tape", "line", " · ".join(extras)))

    picks = biggest_prints(prints, cfg["context_prints"], window_ms, (int(now_ms) or None))
    if picks:
        words = [f"{_fmt_price(row['price'])} × {_fmt_size(row['size'])}"
                 + (f" {row['side']}" if row["side"] else "") for row in picks]
        rows.append(("print", "line", "prints: " + " · ".join(words)))
        for index, row in enumerate(picks, 1):
            rows.append(("print", str(index), f"{_fmt_price(row['price'])} x {_fmt_size(row['size'])} "
                                              f"{row['side']}".strip()))

    walls = nearest_levels(_ctx_get(ctx, "levels"), price, cfg["context_levels"])
    if walls:
        words = []
        for row in walls:
            distance = "" if row["distance_ticks"] == float("inf") else f" ({row['distance_ticks']:.1f}t)"
            size = _fmt_size(row["size"])
            words.append(" ".join(part for part in (row["side"], _fmt_price(row["price"]),
                                                   f"×{size}" if size else "") if part) + distance)
        rows.append(("wall", "line", "walls: " + " · ".join(words)))
        for index, row in enumerate(walls, 1):
            rows.append(("wall", str(index), f"{row['side']} {_fmt_price(row['price'])} x "
                                             f"{_fmt_size(row['size'])}"))

    session = _ctx_get(ctx, "session")
    if session:
        name = _first_text(_session_name(session)) or ""
        pieces = [name]
        if isinstance(session, dict):
            minutes = _num(session.get("minutes_in"), None)
            if minutes:
                pieces.append(f"{int(minutes) // 60}h{int(minutes) % 60:02d}m in")
            vwap = _num(session.get("vwap"), None)
            if vwap:
                pieces.append(f"vwap {_fmt_price(vwap)}")
            low, high = _num(session.get("range_low"), None), _num(session.get("range_high"), None)
            if low is not None and high is not None:
                pieces.append(f"range {_fmt_price(low)}–{_fmt_price(high)}")
        line = "session: " + " · ".join(piece for piece in pieces if piece)
        rows.append(("session", "state", name))
        rows.append(("session", "line", line))
    return rows


def _block_ride(rule: Any, settings: Any = None) -> str:
    """Why this rule's notification would carry no evidence block — empty when it would carry one.

    The one gate the delivery path applies before it renders a block, shared so the rehearsal asks
    the same question the live engine asks. Two ways a block does not ride: the feature is off for
    this rule (or off by the master switch), or none of the rule's own channels is one a block may
    ride — blocks go to telegram, ntfy, email and webhook, never to the panel, which is the surface
    the rule already wrote to.
    """
    cfg = context_config(rule, settings)
    if not cfg["enabled"]:
        return "off"
    channels = [str(channel).strip().lower() for channel in (rule.channels or [])]
    if not any(channel in cfg["context_channels"] for channel in channels):
        return "no-channel"
    return ""


#: What a reader gets when the row builder itself fails — a sentence about the failure, never "".
#: An empty block is stated downstream as "the snapshot was empty for this event", and that is a
#: claim about the market: a fault in this code must not be able to make it. Fits the smallest
#: legal cap (40) whole.
BLOCK_FAILED = "evidence block failed: internal error"


def context_block(event: Any = None, ctx: Any = None, cfg: Any = None,
                  kind: Any = None) -> str:
    """The evidence snapshot that rides with a notification: plain text, or CSV, hard-capped.

    Pure: an event in, a string out — no hub, no clock beyond the event's own stamp. It never raises
    and never invents a reading: a section whose data is absent is simply not in the block, and a
    block with nothing but its head line is a legitimate answer (that is all a rule with no snapshot
    provider and a bare event can honestly say). If the row builder itself fails, both formats carry
    ``BLOCK_FAILED`` — the empty string stays reserved for the genuinely empty block, so no reader
    can state a code fault as an empty snapshot.

    ``kind`` is the alert kind the rule matched (a CVD divergence's payload carries its own ``kind``
    field — bearish/bullish — so the alert kind cannot be read back out of the payload).
    """
    conf = clean(cfg) if not (isinstance(cfg, dict) and "context_max_chars" in cfg) else cfg
    cap = int(conf.get("context_max_chars", DEFAULTS["context_max_chars"]))
    try:
        rows = _block_sections(event, ctx, conf, str(kind or ""))
    except Exception:                       # a block is evidence, never a way for the engine to fall over
        # A fault in this code must not be able to state itself as an empty snapshot (see BLOCK_FAILED).
        return _cap_lines([BLOCK_FAILED], cap)
    if str(conf.get("context_format", "text")).lower() == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["section", "key", "value"])
        for section, key, value in rows:
            # Every reading as its own row, and the composed line beside them: a spreadsheet should
            # not lose the numbers the text form shows inside its sentences.
            writer.writerow([section, key, value])
        return _cap_csv(buffer.getvalue().splitlines(), cap)
    head = next((value for section, key, value in rows if section == "head" and key == "line"), "")
    lines = [head] if head else []
    lines.extend(value for _section, key, value in rows if key == "line" and value != head)
    return _cap_lines(lines, cap)


def notification_text(alert: Any) -> str:
    """What a channel should send: the alert's own sentence, then its evidence block when it has one.

    The one appender lives in the delivery layer: Telegram, ntfy and email build their own bodies and
    append the block with ``notify._with_context``. This is that same rule for a caller holding a
    whole alert, and it delegates there — so a sentence-less alert reads as its block alone (no
    leading blank line) and both renderers can never drift apart.
    """
    data = alert if isinstance(alert, dict) else getattr(alert, "__dict__", {}) or {}
    message = str(data.get("message") or data.get("name") or "")
    from orderflow_system.atlas.notify import _with_context       # the delivery layer's appender
    return _with_context(data, message)


class ContextBuffer:
    """The snapshot the engine reads: the hub feeds it, the checks and the block read it.

    Deliberately small and I/O-free — a per-symbol ring of prints, the level list and an optional
    session block, all capped, nothing derived that can be derived later. ``ctx(symbol)`` is what
    ``AlertEngine.context_provider`` points at:

        alerts = AlertEngine(rules, settings=cfg["alert_builder"])
        buf = ContextBuffer(window_ms=alerts.settings["context_window_ms"])
        alerts.context_provider = buf.ctx
        ... in the tick path:   buf.add_print(symbol, tick.timestamp_ms, tick.price, tick.size, side)
        ... in the book path:   buf.set_levels(symbol, wall_rows)
        ... in the session path: buf.set_session(symbol, {"name": "us", "state": "open"})

    A symbol nobody has fed returns {} — the block then carries only what the event itself says.
    """

    def __init__(self, window_ms: int = 60_000, max_prints: int = 400, max_symbols: int = 12) -> None:
        self.window_ms = max(1_000, int(window_ms))
        self.max_prints = max(10, int(max_prints))
        self.max_symbols = max(1, int(max_symbols))
        self._prints: "OrderedDict[str, deque[dict[str, Any]]]" = OrderedDict()
        self._levels: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
        self._session: dict[str, dict[str, Any]] = {}
        self.added = 0

    # ── feeding (the hub's side) ──────────────────────────────
    def add_print(self, symbol: str, ts_ms: Any, price: Any, size: Any, side: Any = "") -> None:
        """One print. Out-of-order stamps are accepted and sorted out by the readers."""
        key = str(symbol or "").strip().upper()
        stamp = _num(ts_ms, None)
        value = _num(price, None)
        if not key or not stamp or value is None:
            return
        ring = self._prints.get(key)
        if ring is None:
            ring = deque(maxlen=self.max_prints)
            self._prints[key] = ring
        ring.append({"ts_ms": int(stamp), "price": value, "size": _num(size, 0.0) or 0.0,
                     "side": _print_side(side)})
        self.added += 1
        self._prints.move_to_end(key)
        self._evict()

    def set_levels(self, symbol: str, levels: Any) -> None:
        key = str(symbol or "").strip().upper()
        if not key:
            return
        rows = [dict(row) for row in (levels or []) if isinstance(row, dict)][:40]
        self._levels[key] = rows
        self._levels.move_to_end(key)
        self._evict()

    def set_session(self, symbol: str, session: Any) -> None:
        key = str(symbol or "").strip().upper()
        if not key:
            return
        if isinstance(session, dict):
            self._session[key] = dict(session)
        elif session:
            self._session[key] = {"name": str(session)}
        else:
            self._session.pop(key, None)

    def clear(self, symbol: str = "") -> None:
        key = str(symbol or "").strip().upper()
        if not key:
            self._prints.clear()
            self._levels.clear()
            self._session.clear()
            return
        self._prints.pop(key, None)
        self._levels.pop(key, None)
        self._session.pop(key, None)

    def _evict(self) -> None:
        """Keep the most recently fed symbols, so a fuzzed symbol string cannot grow the buffer."""
        for store in (self._prints, self._levels):
            while len(store) > self.max_symbols:
                oldest, _ = next(iter(store.items()))
                store.pop(oldest, None)
                self._session.pop(oldest, None)

    # ── reading (the engine's side) ───────────────────────────
    def ctx(self, symbol: str) -> dict[str, Any]:
        """The snapshot for one symbol: the window's prints, the levels and the session state."""
        key = str(symbol or "").strip().upper()
        if not key:
            return {}
        ring = self._prints.get(key)
        if ring is None and key not in self._levels and key not in self._session:
            return {}
        rows = [dict(row) for row in (ring or [])]
        end = rows[-1]["ts_ms"] if rows else 0
        window = [row for row in rows if row["ts_ms"] > end - self.window_ms] if end else []
        out: dict[str, Any] = {"symbol": key, "window_ms": self.window_ms, "prints": window}
        if end:
            out["now_ms"] = end
        levels = self._levels.get(key)
        if levels:
            out["levels"] = [dict(row) for row in levels]
        session = self._session.get(key)
        if session:
            out["session"] = dict(session)
        if window:
            out["last_price"] = window[-1]["price"]
            out["volume"] = round(sum(row["size"] for row in window), 6)
            out["delta"] = window_delta(window, self.window_ms, end)
        return out

    def stats(self) -> dict[str, Any]:
        return {"symbols": len(self._prints), "prints": sum(len(ring) for ring in self._prints.values()),
                "levels": sum(len(rows) for rows in self._levels.values()),
                "sessions": len(self._session), "added": self.added,
                "window_ms": self.window_ms, "max_prints": self.max_prints}


def context_from_hub(hub: Any, symbol: str, window_ms: int = 60_000, prints: int = 240,
                     walls: int = 4) -> dict[str, Any]:
    """A snapshot built straight off a live ``FeatureHub``, by duck typing.

    Cheaper than feeding a buffer, and it reads only what the hub already holds: the symbol's tape
    ring (``feats.tape.recent``), its last price, the depth map's own fresh wall list and, if the hub
    has one, its session state. Every read is defensive — a hub that has none of it yields {} and the
    block falls back to the event's own numbers, which is the honest answer, not an error.
    """
    out: dict[str, Any] = {"symbol": str(symbol or "").strip().upper(), "window_ms": int(window_ms)}
    feats = None
    try:
        feats = (getattr(hub, "symbols", {}) or {}).get(str(symbol or "").strip().upper())
    except Exception:
        feats = None
    if feats is None:
        return out
    last_price = 0.0
    try:
        last_price = float(getattr(feats, "last_price", 0.0) or 0.0)
    except Exception:
        last_price = 0.0
    try:
        rows = feats.tape.recent(int(prints)) or []
        cleaned = [{"ts_ms": row.get("ts"), "price": row.get("price"), "size": row.get("size"),
                    "side": row.get("side")} for row in rows if isinstance(row, dict)]
        if cleaned:
            out["prints"] = _print_rows(cleaned)
            if not last_price:
                last_price = out["prints"][-1]["price"]
    except Exception:
        pass
    if last_price:
        out["last_price"] = last_price
    try:
        tick = float(getattr(feats, "tick_size", 0.0) or 0.0)
        rows = []
        for wall in (getattr(feats.heatmap, "wall_prices", lambda *a, **k: [])(top=int(walls)) or []):
            price = _num(wall.get("price"), None)
            if price is None:
                continue
            # The depth map's wall list carries price and size only. Which side it is on follows
            # from where it sits against the last trade — no other reading is invented.
            side = "bid" if price <= last_price else "ask"
            rows.append({"price": price, "size": _num(wall.get("size"), 0.0) or 0.0, "side": side,
                         "distance_ticks": round(abs(price - last_price) / tick, 2) if tick else None})
        if rows:
            out["levels"] = rows
    except Exception:
        pass
    try:
        state = getattr(hub, "session_state", None)
        state = state(symbol) if callable(state) else state
        if isinstance(state, dict) and state:
            out["session"] = dict(state)
        elif isinstance(state, str) and state.strip():
            out["session"] = {"name": state.strip()}
    except Exception:
        pass
    return out


class AlertEngine:
    """Evaluates detections against the rule set."""

    def __init__(self, rules: Optional[Iterable[dict[str, Any]]] = None, history: int = 500,
                 webhook_url: str = "", settings: Any = None) -> None:
        self.rules: list[AlertRule] = [AlertRule.from_dict(r) for r in (rules if rules is not None else DEFAULT_RULES)]
        self.history: list[Alert] = []
        self._history_max = history
        # the reference layout parity: indicator alerts can be forwarded to an external
        # automation service. Anything with "webhook" in its channels is POSTed.
        self.webhook_url = webhook_url or ""
        self.webhook_stats = {"sent": 0, "failed": 0, "last_error": ""}
        # price-touch alerts (`level_touch`): per-rule band state, so a rule fires on the
        # outside-to-inside transition and re-arms once price leaves the band again.
        self._touch_inside: dict[str, bool] = {}
        #: The newest raw event of each kind the engine has itself evaluated (kind -> (payload,
        #: stamp)) — what the builder's rehearsal reads, so a dry run sees the same event shape the
        #: live path saw rather than the alert record's scalarised copy. Bounded by kinds, not by
        #: events: one entry per kind, replaced as newer ones arrive.
        self._last_events: dict[str, tuple[Any, int]] = {}
        #: This feature's settings block (``atlas.alert_builder``), coerced by ``clean``. It governs
        #: the evidence block and the ceiling on conditions; the rules themselves live above.
        self.settings: dict[str, Any] = clean(settings)
        #: Where the snapshot for conditions and evidence comes from. The hub sets this to a
        #: ``ContextBuffer.ctx`` (or ``context_from_hub``); without one the engine still works and
        #: the block carries whatever the event itself says.
        self.context_provider: Optional[Callable[[str], dict[str, Any]]] = None
        #: Cooldown state, keyed by rule (or by rule+symbol when a rule asks for its own per-instrument
        #: clock). Kept beside ``rule.last_fired_ms`` — the rule's own field stays what the UI shows.
        self._last_fire: dict[str, int] = {}
        #: Once-per-window state: key -> (the window index it counts, fires inside that window).
        self._window_fires: dict[str, tuple[int, int]] = {}
        #: Rules the engine could not read for an event — a param that is not a number, a shape the
        #: reader does not expect. Counted per rule and skipped (never raised): the count is what a
        #: surface can point at instead of silence, and one bad rule cannot stop the tick.
        self._unreadable: dict[str, int] = {}
        #: How many alerts have carried an evidence block (the honest answer to "is it on?").
        self.context_blocks = 0

    # ── rule management ───────────────────────────────────────
    def set_rules(self, rules: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        self.rules = [AlertRule.from_dict(r) for r in rules]
        self._prune_fire_state()
        return [r.to_dict() for r in self.rules]

    def upsert(self, rule: dict[str, Any]) -> list[dict[str, Any]]:
        """Create a rule, or patch an existing one by id (partial bodies merge)."""
        rid = (rule or {}).get("id")
        existing = next((r for r in self.rules if r.id == rid), None) if rid else None
        if existing is not None:
            merged = existing.to_dict()
            merged.update({k: v for k, v in rule.items() if v is not None})
            parsed = AlertRule.from_dict(merged)
            parsed.fired, parsed.last_fired_ms = existing.fired, existing.last_fired_ms
            self.rules[self.rules.index(existing)] = parsed
        else:
            parsed = AlertRule.from_dict(rule)
            self.rules.append(parsed)
        return [r.to_dict() for r in self.rules]

    def remove(self, rule_id: str) -> list[dict[str, Any]]:
        self.rules = [r for r in self.rules if r.id != rule_id]
        self._touch_inside.pop(rule_id, None)
        self._prune_fire_state()
        return [r.to_dict() for r in self.rules]

    # ── evaluation ────────────────────────────────────────────
    def evaluate(self, symbol: str, kind: str, payload: Any, ts_ms: Optional[int] = None,
                 ctx: Optional[dict[str, Any]] = None) -> list[Alert]:
        """Check one detection against every enabled rule of that kind.

        ``ctx`` is the snapshot a rule's conditions and its evidence block read. Left out, the engine
        asks its own ``context_provider`` — and only for a kind some enabled rule has conditions or a
        context request for, so the 24 shipped rules cost nothing for carrying the feature.
        """
        ts = int(ts_ms or time.time() * 1000)
        self._last_events[kind] = (copy.deepcopy(payload), ts)
        if ctx is None:
            ctx = self._context_for(symbol, ts) if self._snapshot_wanted(kind) else {"symbol": symbol}
        fired: list[Alert] = []
        for rule in self.rules:
            if not rule.enabled or rule.kind != kind:
                continue
            params = rule.params or {}
            try:
                # The two generic scopes (a bound price, a minimum hold) refuse first, from the
                # same implementation the builder's rehearsal reads — see ``_scope_gates``.
                if any(not gate["ok"] for gate in _scope_gates(params, payload)):
                    continue
                if not self._passes(rule.kind, params, payload):
                    continue
                if not self._conditions_pass(rule, payload, ctx, symbol, ts):
                    continue
                message = self._message(rule, symbol, payload)
                severity = "critical" if kind in ("stop_run", "block_trade") else "warning" if kind in (
                    "sweep", "iceberg", "stacked_imbalance", "intent_pressure", "trapped_traders",
                    "depth_execution", "depth_refill") else "info"
                alert = Alert(rule_id=rule.id, name=rule.name, kind=kind, symbol=symbol, ts_ms=ts,
                              message=message, severity=severity, data=_safe(payload),
                              channels=list(rule.channels),
                              context=self._evidence(rule, payload, ctx, kind, symbol))
            except Exception:
                # An authored value this reader cannot use — a threshold that is not a number, a
                # shape it does not expect — makes the rule unreadable for this event: counted and
                # skipped, never raised. Nothing raises on a market event, and one bad rule must
                # not stop the tick for every other rule (or the whole detection loop).
                self._note_unreadable(rule, kind)
                continue
            self._note_fired(rule, symbol, ts)
            fired.append(alert)
            self.history.append(alert)
        if len(self.history) > self._history_max:
            self.history = self.history[-self._history_max:]
        return fired

    def evaluate_touch(self, symbol: str, price: float, ts_ms: Optional[int] = None,
                       ctx: Optional[dict[str, Any]] = None) -> list[Alert]:
        """Price-touch alerts: a ``level_touch`` rule fires when price RETURNS into its band.

        The area profile's "watch this level" hand-off writes these rules. The event is the
        transition — outside the band to inside it — so price resting at the level fires once,
        not once per tick; leaving the band re-arms it, and the rule's own cooldown still applies.
        The band is the rule's own ``at_price ± at_tol`` (the same scope every rule carries); a
        rule without a level can never fire and is skipped rather than guessed at.
        """
        ts = int(ts_ms or time.time() * 1000)
        if ctx is None:
            ctx = self._context_for(symbol, ts) if self._snapshot_wanted("level_touch") else {"symbol": symbol}
        fired: list[Alert] = []
        for rule in self.rules:
            if not rule.enabled or rule.kind != "level_touch":
                continue
            params = rule.params or {}
            try:
                level = params.get("at_price")
                if level is None:
                    continue
                tol = float(params.get("at_tol", 0) or 0)
                inside = abs(float(price) - float(level)) <= tol
                was_inside = self._touch_inside.get(rule.id, False)
                self._touch_inside[rule.id] = inside
                if not inside or was_inside:
                    continue
                touch_event = {"price": float(level), "last": float(price), "at_tol": tol}
                self._last_events["level_touch"] = (copy.deepcopy(touch_event), ts)
                if not self._conditions_pass(rule, touch_event, ctx, symbol, ts):
                    continue
                alert = Alert(rule_id=rule.id, name=rule.name, kind="level_touch", symbol=symbol, ts_ms=ts,
                              message=self._message(rule, symbol, touch_event), severity="info",
                              data=touch_event, channels=list(rule.channels),
                              context=self._evidence(rule, touch_event, ctx, "level_touch", symbol))
            except Exception:
                # Same class as evaluate's guard: an unreadable band (a level that is not a number)
                # is counted and skipped, never raised out of the tick path.
                self._note_unreadable(rule, "level_touch")
                continue
            self._note_fired(rule, symbol, ts)
            fired.append(alert)
            self.history.append(alert)
        if fired and len(self.history) > self._history_max:
            self.history = self.history[-self._history_max:]
        return fired

    def recent(self, limit: int = 100, symbol: str = "") -> list[dict[str, Any]]:
        rows = [a for a in self.history if not symbol or a.symbol == symbol]
        return [a.to_dict() for a in rows[-limit:]]

    async def dispatch_webhooks(self, alerts: Iterable[Alert], timeout_s: float = 5.0) -> int:
        """POST fired alerts to the configured webhook.

        the reference layout forwards indicator alerts to an external automation service; rules opt
        in with ``"webhook"`` in their channels. Failures are counted, never raised —
        an unreachable webhook must not affect the trading pipeline.
        """
        if not self.webhook_url:
            return 0
        targets = [a for a in alerts if "webhook" in (a.channels or [])]
        if not targets:
            return 0
        sent = 0
        try:
            import aiohttp
        except Exception as exc:                       # pragma: no cover - dep is present
            self.webhook_stats["failed"] += len(targets)
            self.webhook_stats["last_error"] = f"aiohttp unavailable: {exc}"
            return 0
        try:
            timeout = aiohttp.ClientTimeout(total=timeout_s)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for alert in targets:
                    payload = self.webhook_payload(alert)
                    try:
                        async with session.post(self.webhook_url, json=payload) as resp:
                            if resp.status < 400:
                                sent += 1
                            else:
                                self.webhook_stats["failed"] += 1
                                self.webhook_stats["last_error"] = f"HTTP {resp.status}"
                    except Exception as exc:
                        self.webhook_stats["failed"] += 1
                        self.webhook_stats["last_error"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:                        # pragma: no cover - session failure
            self.webhook_stats["failed"] += len(targets)
            self.webhook_stats["last_error"] = f"{type(exc).__name__}: {exc}"
        self.webhook_stats["sent"] += sent
        return sent

    def stats(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for a in self.history:
            counts[a.kind] = counts.get(a.kind, 0) + 1
        return {"rules": len(self.rules), "enabled": sum(1 for r in self.rules if r.enabled),
                "history": len(self.history), "by_kind": counts,
                "webhook": dict(self.webhook_stats),
                "webhook_rules": sum(1 for r in self.rules if "webhook" in (r.channels or [])),
                # the builder's own numbers: how many rules ask for more than their kind, and how
                # many alerts actually carried evidence (0 proves the feature is off, not "unknown")
                "condition_rules": sum(1 for r in self.rules if r.conditions),
                "context_rules": sum(1 for r in self.rules
                                     if context_config(r, self.settings)["enabled"]),
                "context_blocks": self.context_blocks,
                # Rules skipped as unreadable (a threshold that is not a number), per rule — the
                # count a surface can point at instead of silence. Empty while every rule reads.
                "unreadable": dict(self._unreadable)}

    def to_csv(self, limit: int = 500) -> str:
        """CSV export of the alert log (the reference layout exposes CSV export for its feeds)."""
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["ts_ms", "time", "severity", "kind", "symbol", "rule", "message"])
        for a in self.history[-limit:]:
            writer.writerow([a.ts_ms, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(a.ts_ms / 1000)),
                             a.severity, a.kind, a.symbol, a.name, a.message])
        return buf.getvalue()

    def webhook_payload(self, alert: Alert) -> dict[str, Any]:
        return {"source": "orderflow-analysis-pro", "type": "orderflow_alert", **alert.to_dict()}

    # ── the builder's rehearsal ───────────────────────────────
    def test_fire(self, rule: Any = None, event: Any = None, symbol: str = "",
                  ts_ms: Optional[int] = None) -> dict[str, Any]:
        """Rehearse one candidate rule against the live snapshot. Nothing fires, nothing is recorded.

        This is what the builder's Test fire button calls. The event is the one handed in, or — with
        none — the newest real event of that kind the engine itself has evaluated (the alert log is
        the fallback for a kind nothing has been evaluated for since boot), so a rehearsal reads the
        same event, same shape, the live path read rather than a made-up payload; with no such event
        the answer is a refusal that says so, never a guess dressed as a result.

        The answer carries every gate's verdict, the per-condition readings, and the evidence block
        only when a notification would really carry one — the same gate the delivery path applies,
        reported as ``context_gate`` (``off`` when the evidence feature is off for this rule or by
        the master switch, ``no-channel`` when none of the rule's channels is one a block may ride,
        empty when a block would ride).
        """
        try:
            candidate = rule if isinstance(rule, AlertRule) else AlertRule.from_dict(rule or {})
        except Exception:
            return {"ok": False, "error": "that rule could not be read — check its kind and params"}
        ts = int(ts_ms or time.time() * 1000)
        rehearsal, origin, event_ts = self._rehearsal_event(candidate, event)
        if rehearsal is None:
            return {"ok": False, "kind": candidate.kind, "rule": candidate.to_dict(),
                    "error": f"no {str(candidate.kind).replace('_', ' ')} event has been seen yet, so "
                             "there is nothing real to rehearse against — the rule is saved and the "
                             "engine will evaluate it on the live stream"}
        sym = str(symbol or _first_text(_event_get(rehearsal, "symbol")) or "").strip().upper()
        ctx = self._context_for(sym, event_ts or ts)
        conf = context_config(candidate, self.settings)
        ride = _block_ride(candidate, self.settings)
        try:
            thresholds = bool(self._passes(candidate.kind, candidate.params or {}, rehearsal))
            conditions = condition_results(candidate, rehearsal, ctx, self.settings)
            conditions_ok = evaluate_conditions(candidate, rehearsal, ctx, self.settings)
            cooling = self._cooldown_ok(candidate, sym, ts)
            message = self._message(candidate, sym, rehearsal)
            gates = [
                {"gate": "kind", "ok": True,
                 "detail": f"the rule listens for {candidate.kind.replace('_', ' ')} and this is one"},
                *_scope_gates(candidate.params or {}, rehearsal),
                {"gate": "thresholds", "ok": thresholds,
                 "detail": "the event clears the rule's own thresholds" if thresholds
                           else "the event does not clear the rule's own thresholds"},
                {"gate": "conditions", "ok": conditions_ok,
                 "detail": "no conditions on this rule" if not conditions else
                           _conditions_detail(candidate, conditions_ok)},
                {"gate": "cooldown", "ok": cooling,
                 "detail": "nothing else is holding it back" if cooling else
                           "its cooldown or its once-per-window is still running"},
            ]
        except Exception:
            # The same unreadable-rule class evaluate quarantines, seen from the rehearsal: a
            # threshold that is not a number has no verdict to show. Refuse with a sentence —
            # never a traceback dressed as a result, never an invented "the market said no".
            return {"ok": False, "kind": candidate.kind, "rule": candidate.to_dict(),
                    "error": "this rule's own params could not be read — check that every "
                             "threshold is a number — nothing can be rehearsed until they are"}
        return {"ok": True, "fires": all(gate["ok"] for gate in gates), "gates": gates,
                "conditions": conditions,
                "context": "" if ride else context_block(rehearsal, ctx, conf, candidate.kind),
                "context_gate": ride,
                "message": message, "kind": candidate.kind,
                "symbol": sym, "origin": origin, "ts_ms": ts, "event": _safe(rehearsal),
                "settings": {key: value for key, value in conf.items()},
                "rule": candidate.to_dict()}

    def _rehearsal_event(self, rule: AlertRule, event: Any = None) -> tuple[Any, str, int]:
        """The event a dry run reads: the one handed in, else the newest real event of that kind.

        The newest real event is the payload the engine itself last evaluated — the same shape the
        live path read, nested values and all — so a rehearsal can never read a string where the
        live engine read a structure. The alert log is the fallback for a kind nothing has been
        evaluated for since boot; its entries carry the record's scalarised copy, and the answer says
        ``alert`` rather than ``event`` so the two are never confused.
        """
        if event is not None:
            stamp = int(_num(_event_get(event, "ts_ms"), 0) or 0)
            return event, "the event handed to the test", stamp
        seen = self._last_events.get(rule.kind)
        if seen is not None:
            payload, stamp = seen
            age_s = max(0, int((time.time() * 1000 - int(stamp)) / 1000))
            when = f"{age_s}s ago" if age_s < 600 else f"{age_s // 60}min ago"
            return copy.deepcopy(payload), f"the newest {rule.kind.replace('_', ' ')} event ({when})", \
                int(stamp)
        for alert in reversed(self.history):
            if alert.kind == rule.kind:
                age_s = max(0, int((time.time() * 1000 - int(alert.ts_ms)) / 1000))
                when = f"{age_s}s ago" if age_s < 600 else f"{age_s // 60}min ago"
                return dict(alert.data), f"the newest {rule.kind.replace('_', ' ')} alert ({when})", \
                    int(alert.ts_ms)
        return None, "", 0

    # ── internals ─────────────────────────────────────────────
    def _snapshot_wanted(self, kind: str) -> bool:
        """True when some enabled rule of this kind reads a snapshot — the provider is only asked then."""
        if self.context_provider is None:
            return False
        return any(rule.enabled and rule.kind == kind and (rule.conditions or rule.context is not None)
                   for rule in self.rules)

    def _context_for(self, symbol: str, ts_ms: int) -> dict[str, Any]:
        """The snapshot a rule's conditions and its block read. Best effort: no provider, or a
        provider that raises, leaves the block with what the event itself carries plus the symbol."""
        out: dict[str, Any] = {"symbol": symbol} if symbol else {}
        provider = self.context_provider
        if provider is None:
            return out
        try:
            ctx = provider(symbol)
        except Exception:
            logger.debug("alert context provider failed for %s", symbol, exc_info=True)
            return out
        if not isinstance(ctx, dict):
            return out
        out.update(ctx)
        if symbol:
            out.setdefault("symbol", symbol)
        if ts_ms:
            out.setdefault("now_ms", int(ts_ms))
        return out

    def _conditions_pass(self, rule: AlertRule, event: Any, ctx: Any, symbol: str, ts_ms: int) -> bool:
        """The rule's own gates: its conditions, then its cooldown / once-per-window clock."""
        if not evaluate_conditions(rule, event, ctx, self.settings):
            return False
        return self._cooldown_ok(rule, symbol, ts_ms)

    def _evidence(self, rule: AlertRule, event: Any, ctx: Any, kind: str, symbol: str = "") -> str:
        """The block this alert carries — when the rule asked for one and it is leaving the screen."""
        if _block_ride(rule, self.settings):
            return ""
        cfg = context_config(rule, self.settings)
        snapshot = dict(ctx) if isinstance(ctx, dict) else {}
        if symbol:
            snapshot.setdefault("symbol", symbol)
        block = context_block(event, snapshot, cfg, kind)
        if block:
            self.context_blocks += 1
        return block

    def _cooldown_ok(self, rule: AlertRule, symbol: str, ts_ms: int) -> bool:
        """The rule's fire gate: the sliding cooldown, plus the optional once-per-window clock.

        ``cooldown_s`` is the original behaviour — N seconds since the last fire, counted per rule or
        (with ``cooldown_scope: "symbol"``) per instrument, so a busy symbol cannot mute a quiet one.
        ``once_per_window_s`` is the aligned one: at most ``max_per_window`` fires inside each window
        that starts at ``ts // window``, which is what "once per 5-minute bar" means — a sliding
        cooldown would let the next bar fire five seconds later.
        """
        key = _fire_key(rule.id, symbol, rule.cooldown_scope)
        last = int(self._last_fire.get(key) or 0)
        if rule.cooldown_s > 0 and last and ts_ms - last < float(rule.cooldown_s) * 1000:
            return False
        window_ms = int(float(rule.once_per_window_s or 0) * 1000)
        if window_ms > 0:
            index, used = self._window_fires.get(key, (-1, 0))
            if index == ts_ms // window_ms and used >= max(1, int(rule.max_per_window or 1)):
                return False
        return True

    def _note_unreadable(self, rule: AlertRule, kind: str) -> None:
        """Count a rule the engine skipped as unreadable for this event. Logged, never raised."""
        self._unreadable[rule.id] = self._unreadable.get(rule.id, 0) + 1
        logger.debug("alert rule %r (%s) could not be read for this event — skipped",
                     rule.id, kind, exc_info=True)

    def _note_fired(self, rule: AlertRule, symbol: str, ts_ms: int) -> None:
        """Record one fire, in the rule's own fields and in the cooldown / window state."""
        key = _fire_key(rule.id, symbol, rule.cooldown_scope)
        self._last_fire[key] = int(ts_ms)
        window_ms = int(float(rule.once_per_window_s or 0) * 1000)
        if window_ms > 0:
            index, used = self._window_fires.get(key, (-1, 0))
            self._window_fires[key] = (ts_ms // window_ms, used + 1 if index == ts_ms // window_ms else 1)
        rule.last_fired_ms = int(ts_ms)
        rule.fired += 1
        if len(self._last_fire) > 8 * max(1, len(self.rules)) + 16:
            self._prune_fire_state()

    def _prune_fire_state(self) -> None:
        """Drop cooldown keys whose rule is gone; the maps are small, but they are per rule id."""
        ids = {rule.id for rule in self.rules}
        for key in [key for key in self._last_fire if key.split("|", 1)[0] not in ids]:
            self._last_fire.pop(key, None)
        for key in [key for key in self._window_fires if key.split("|", 1)[0] not in ids]:
            self._window_fires.pop(key, None)
        for rid in [rid for rid in self._unreadable if rid not in ids]:
            self._unreadable.pop(rid, None)

    @staticmethod
    def _passes(kind: str, params: dict[str, Any], payload: Any) -> bool:
        get = (lambda key, default=None: payload.get(key, default)) if isinstance(payload, dict) else (lambda key, default=None: getattr(payload, key, default))
        if kind in ("big_trade", "block_trade"):
            if get("multiple", 1.0) < float(params.get("min_multiple", 0) or 0):
                return False
            sides = params.get("sides")
            if sides and str(get("side", "")).lower() not in [s.lower() for s in sides]:
                return False
            if float(get("size", 0) or 0) < float(params.get("min_size", 0) or 0):
                return False
            return True
        if kind == "sweep":
            return int(get("levels", 0) or 0) >= int(params.get("min_levels", 0) or 0) and \
                float(get("size", 0) or 0) >= float(params.get("min_size", 0) or 0)
        if kind == "stop_run":
            return float(get("ticks_moved", 0) or 0) >= float(params.get("min_ticks", 0) or 0)
        if kind == "iceberg":
            return int(get("fills", 0) or 0) >= int(params.get("min_fills", 0) or 0)
        if kind == "speed_spike":
            return float(get("zscore", 0) or 0) >= float(params.get("min_zscore", 0) or 0)
        if kind == "cvd_divergence":
            kinds = params.get("kinds") or []
            if kinds and get("kind", "") not in kinds:
                return False
            return float(get("strength", 0) or 0) >= float(params.get("min_strength", 0) or 0)
        if kind in ("heat_pull", "heat_stack"):
            return float(get("size", 0) or 0) >= float(params.get("min_size", 0) or 0)
        if kind == "wall_age":
            # the same size floor the heatmap's hold-alert writes (it defaults it to 80 % of the
            # selected level), on a kind whose event is the level still holding
            return float(get("size", 0) or 0) >= float(params.get("min_size", 0) or 0)
        if kind == "wall":
            return float(get("size", 0) or 0) >= float(params.get("min_size", 0) or 0)
        if kind == "vwap_cross":
            return abs(float(get("ticks", 0) or 0)) >= float(params.get("min_ticks", 0) or 0)
        if kind in ("depth_execution", "depth_refill"):
            return float(get("share", 0) or 0) >= float(params.get("min_share", 0) or 0)
        if kind == "stacked_imbalance":
            return int(get("levels", 0) or 0) >= int(params.get("min_levels", 0) or 0) and \
                float(get("volume", 0) or 0) >= float(params.get("min_volume", 0) or 0)
        if kind == "intent_pressure":
            return float(get("pct", 0) or 0) >= float(params.get("min_pct", 0) or 0)
        if kind == "pulled_size":
            return float(get("size", 0) or 0) >= float(params.get("min_size", 0) or 0) and \
                float(get("distance_ticks", 99) or 99) <= float(params.get("max_distance_ticks", 99) or 99)
        if kind == "trapped_traders":
            return float(get("beyond_ticks", 0) or 0) >= float(params.get("min_beyond_ticks", 0) or 0)
        if kind == "unfinished_business":
            sides = params.get("sides") or []
            if sides and str(get("side", "")).lower() not in [s.lower() for s in sides]:
                return False
            return int(get("arms", 1) or 1) >= int(params.get("min_arms", 0) or 0)
        if kind == "node_zone":
            return int(get("count", 0) or 0) >= int(params.get("min_count", 0) or 0)
        if kind == "level_touch":
            # its threshold IS the level (at_price ± at_tol, checked generically) and the event
            # is the touch itself, so this kind has no knob of its own to read.
            return True
        if kind == "radar_level":
            states = params.get("states") or []
            if states and str(get("state", "")) not in [str(s) for s in states]:
                return False
            return True
        return True

    @staticmethod
    def _message(rule: AlertRule, symbol: str, payload: Any) -> str:
        """The one-line story of a fire — never a dangling ``": "`` when the rule names no symbol."""
        text = AlertEngine._message_body(rule, symbol, payload)
        return text[2:] if text.startswith(": ") else text

    @staticmethod
    def _message_body(rule: AlertRule, symbol: str, payload: Any) -> str:
        get = (lambda key, default=None: payload.get(key, default)) if isinstance(payload, dict) else (lambda key, default=None: getattr(payload, key, default))
        k = rule.kind
        if k in ("big_trade", "block_trade"):
            return (f"{symbol}: {get('side', '?').upper()} {_fmt_size(get('size'))} @ {_fmt_price(get('price'))} "
                    f"({_fmt_num(get('multiple'))}× big-trade threshold)")
        if k == "sweep":
            return (f"{symbol}: {get('side', '?').upper()} sweep through {_fmt_num(get('levels'))} levels "
                    f"({_fmt_size(get('size'))} in {_fmt_num(get('duration_ms'))}ms)")
        if k == "stop_run":
            note = get("note", "") or ""
            return (f"{symbol}: stop run {get('direction')} {_fmt_num(get('ticks_moved'))} ticks in "
                    f"{_fmt_num(get('duration_ms'))}ms" + (f" — {note}" if note else ""))
        if k == "iceberg":
            return (f"{symbol}: iceberg inference — {_fmt_num(get('fills'))} refills @ {_fmt_price(get('price'))} "
                    f"(modal {_fmt_size(get('modal_size'))})")
        if k == "speed_spike":
            return (f"{symbol}: speed of tape z={_fmt_num(get('zscore'))} "
                    f"({_fmt_size(get('volume_5s'))} in 5s)")
        if k == "cvd_divergence":
            return f"{symbol}: {get('kind')} CVD divergence — {get('note')}"
        if k in ("heat_pull", "heat_stack"):
            return f"{symbol}: {get('detail', k)} @ {_fmt_price(get('price'))}"
        if k == "wall_age":
            detail = get("detail", "") or ""
            if not detail:
                held = get("held_ms")
                detail = (f"held {float(held) / 60000.0:.1f} min"
                          if isinstance(held, (int, float)) and not isinstance(held, bool) and held
                          else "level still holding")
            return f"{symbol}: {detail} @ {_fmt_price(get('price'))}"
        if k == "vwap_cross":
            return (f"{symbol}: price crossed {'above' if get('side') == 'above' else 'below'} VWAP "
                    f"({float(get('ticks', 0)):+.2f} ticks, VWAP {_fmt_price(get('vwap'))})")
        if k == "depth_execution":
            return (f"{symbol}: {str(get('side', '')).upper()} print of {_fmt_size(get('size'))} took "
                    f"{float(get('share', 0)) * 100:.0f}% of the {_fmt_size(get('resting'))} resting at "
                    f"{_fmt_price(get('price'))}")
        if k == "depth_refill":
            return (f"{symbol}: level {_fmt_price(get('price'))} refilled "
                    f"{float(get('refill_ms', 0)) / 1000:.1f}s after being eaten "
                    f"({_fmt_size(get('size'))} traded) — refreshed liquidity (inferred)")
        if k == "stacked_imbalance":
            return (f"{symbol}: stacked {str(get('side', '')).upper()} imbalance over {get('levels')} levels "
                    f"({_fmt_price(get('from_price'))} → {_fmt_price(get('to_price'))}, "
                    f"peak {_fmt_num(get('max_ratio_pct'))}%)")
        if k == "intent_pressure":
            side = "buy side" if str(get("side", "")) == "bid" else "sell side"
            return (f"{symbol}: {side} of the book at {_fmt_num(get('pct'))}% of its normal weight "
                    f"(threshold {_fmt_num(get('threshold'))}%) — buyers/sellers are showing size")
        if k == "pulled_size":
            return (f"{symbol}: {_fmt_size(get('size'))} pulled from the {get('side')} "
                    f"{_fmt_num(get('distance_ticks'))} ticks from mid @ {_fmt_price(get('price'))} "
                    f"without being traded")
        if k == "trapped_traders":
            return (f"{symbol}: {get('side')} trapped — break past {_fmt_price(get('level'))} failed, "
                    f"reclaimed in {round((get('reclaim_ms') or 0) / 1000)}s")
        if k == "unfinished_business":
            side = "high" if str(get("side", "")) == "above" else "low"
            finish = "bid" if side == "high" else "ask"
            return (f"{symbol}: unfinished {side} at {_fmt_price(get('price'))} — the auction never finished "
                    f"(no zero-on-{finish} completion); it clears when price returns")
        if k == "node_zone":
            count = int(get("count", 0) or 0)
            label = {2: "double", 3: "triple"}.get(count, f"{count}-bar")
            return (f"{symbol}: {label} node at {_fmt_price(get('price'))} "
                    f"({count} consecutive bars at one price)")
        if k == "level_touch":
            return f"{symbol}: price came back to the watched level {get('price')} (±{get('at_tol')})"
        if k == "radar_level":
            state = str(get("state", ""))
            source = str(get("source", "level")).replace("_", " ")
            price = _fmt_price(get("price"))
            if state == "armed":
                return f"{symbol}: new {source} level armed at {price}"
            if state in ("defended", "confirmed"):
                extra = " — first test" if get("first_test") else (
                    f" (test {get('touches')})" if get("touches") else "")
                return (f"{symbol}: {source} level {price} "
                        f"{'confirmed' if state == 'confirmed' else 'held'}{extra}")
            if state == "spent":
                return f"{symbol}: {source} level {price} spent — traded through"
            if state == "failed":
                return f"{symbol}: {source} level {price} failed — held once, then broken through"
            return f"{symbol}: {source} level {price} {state}"
        return f"{symbol}: {rule.name}"


def _safe(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return {k: (v if isinstance(v, (int, float, str, bool, type(None))) else str(v)) for k, v in payload.items()}
    if hasattr(payload, "__dict__"):
        return {k: (v if isinstance(v, (int, float, str, bool, type(None))) else str(v)) for k, v in payload.__dict__.items()}
    return {}
