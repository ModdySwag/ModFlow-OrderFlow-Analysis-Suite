"""Footprint configuration — the settings block behind the panel's drawer, and the per-cell reading.

WHAT THIS IS
  Every knob the footprint panel's settings drawer shows, in one block the config store can keep
  (`atlas.footprint`), plus the pure reading that turns a bar's price rows into marks: which rows
  are imbalanced (same-price or diagonal), which of those form a stack, which read as absorption,
  where the bar's POC and its value area are, and which rows are the bar's extremes. The deep
  per-bar configuration is what the paid tiers of the reference programs sell on — bar construction,
  cell metric, imbalance ratio, stacked and diagonal imbalance, size filters, per-bar POC/value area —
  so all of it is a control here, with the plain-language label and the one-line meaning in `CATALOG`.

HOW IT IS SHAPED (and why)
  * `clean()` is the contract: it never raises, drops unknown keys and clamps every number onto
    `DEFAULTS`, so a hand-edited config or a stale drawer cannot put the panel into a state it
    cannot draw. The parent registers this block; this module never reads the config itself.
  * Everything the panel marks is arithmetic over a plain `levels` list of dicts
    (``{"price", "bid", "ask", "volume", "delta", "count"}``) — or the same shape as a
    price->(bid, ask) mapping. No feeds, no hub, no files: the same code serves live bars, demo
    bars, stored bars and a test fixture.
  * The imbalance rules are the ones `analytics/footprint.py` already prints under the panel
    ("calc: ..."): same-price compares a row's ask against its own bid, diagonal compares a row's
    ask against the bid one row below (and its bid against the ask one row above), with the row's
    own side standing in when the neighbouring row is missing. A mark that disagreed with the
    printed count would be a lie, so `test_footprint_config.py` holds the two equal on one fixture.
  * POC and the value area are read on TOTAL traded volume (bid + ask) — the same rule the profile
    engine and the bar's own `calc.poc` use. A delta or a count cell colours a row; it does not
    move the POC. The value area expands from the POC one row at a time, taking the heavier
    neighbour, and prefers the upper row on a tie (the rule `analytics/volume_profile.py` uses).
  * Absorption mirrors the chart's own purple cells (`desktop/ui`'s footprint renderer considers a
    row absorbed once it is `absorption_threshold` times the bar's average row AND the bar's body
    stays inside `absorption_max_body_pct` of its range). With the shipped defaults the two agree
    exactly; the test pins it.
  * A row under `min_level_volume` is not read at all (imbalance, stacks, POC, value area, the
    absorption average), and the block states how many were left out — never a silent drop.
  * `min_print_size` is the one knob this module cannot apply: it filters at aggregation time
    (`FootprintEngine`, via the engine's settings push), so it applies when the engine next reads
    its settings and `capabilities()` says `restart` for it.
  * `count` is offered as a cell metric and is only readable when the bars carry print counts. When
    they do not, the metric reads None and the block says so in one sentence — no invented counts.

REFUSALS
  Nothing here 500s on a missing key or an unreadable payload: a bar with no usable rows answers
  ``ok: false`` with one plain sentence, and the drawer prints that sentence instead of drawing a
  cell.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
from typing import Any, Mapping, Sequence

from fastapi import APIRouter, Body, Query

router = APIRouter(prefix="/api/atlas", tags=["atlas"])

#: What a cell is read for. `bid_ask` is the panel's shipped two-sided read; the four single
#: metrics are the ones the other platforms' Numbers Bars offer under "cell metric".
CELL_METRICS: tuple[str, ...] = ("bid_ask", "bid", "ask", "delta", "volume", "count")

#: Which comparison flags an imbalance. `both` marks the two readings at once — same-price rows
#: keep their own colour, the diagonal reading rides on top of them.
IMBALANCE_MODES: tuple[str, ...] = ("same_price", "diagonal", "both")

#: How the cells are tinted: the shipped two-sided look, the chosen metric, or the imbalance reading.
COLOR_BY: tuple[str, ...] = ("sides", "metric", "imbalance")

#: Which bars the marks are drawn on: every bar, only bars inside the session window, or only bars
#: outside it. The window is a pair of clock times in UTC minutes from midnight, so the filter
#: needs no calendar and works the same for 24 h instruments (where nothing is outside).
SESSION_FILTERS: tuple[str, ...] = ("all", "rth", "outside_rth")

DEFAULTS: dict[str, Any] = {
    "cell_metric": "bid_ask",
    "color_by": "sides",
    "imbalance_mode": "same_price",
    "imbalance_threshold": 3.0,
    "diagonal_ratio": 3.0,
    "stack_min_levels": 3,
    "diagonal_stack_min_levels": 3,
    "min_print_size": 0.0,
    "min_level_volume": 0.0,
    "absorption_threshold": 2.0,
    "absorption_max_body_pct": 0.3,
    "poc_per_bar": True,
    "value_area_per_bar": True,
    "value_area_pct": 0.70,
    "ticks_per_row": 1,
    "session_filter": "all",
    "session_start_min": 810,          # 13:30 UTC — the US cash open
    "session_end_min": 1200,           # 20:00 UTC — the US cash close
    "equal_tolerance": 0.0,
    "show_equal": True,
    "show_extremes": True,
}

#: key -> (low, high, step). `clean()` clamps into these; the drawer's inputs print the same bounds,
#: so what a control shows is what a save keeps. The bounds of the six keys that predate this module
#: are the ones the param registry already publishes, so the two cannot disagree.
BOUNDS: dict[str, tuple[float, float, float]] = {
    "imbalance_threshold": (1.0, 50.0, 0.5),
    "diagonal_ratio": (1.0, 50.0, 0.5),
    "stack_min_levels": (1.0, 20.0, 1.0),
    "diagonal_stack_min_levels": (1.0, 20.0, 1.0),
    "min_print_size": (0.0, 1000.0, 0.001),
    "min_level_volume": (0.0, 1000.0, 0.001),
    "absorption_threshold": (1.0, 20.0, 0.5),
    "absorption_max_body_pct": (0.0, 1.0, 0.05),
    "value_area_pct": (0.5, 0.95, 0.05),
    "ticks_per_row": (1.0, 50.0, 1.0),
    "session_start_min": (0.0, 1439.0, 5.0),
    "session_end_min": (0.0, 1439.0, 5.0),
    "equal_tolerance": (0.0, 1.0, 0.1),
}

#: Keys whose value is a count of rows / ticks / minutes: clamped, then made whole.
WHOLE_KEYS: frozenset[str] = frozenset({
    "stack_min_levels", "diagonal_stack_min_levels", "ticks_per_row",
    "session_start_min", "session_end_min",
})

#: key -> the values an enum key accepts.
CHOICES: dict[str, tuple[str, ...]] = {
    "cell_metric": CELL_METRICS,
    "color_by": COLOR_BY,
    "imbalance_mode": IMBALANCE_MODES,
    "session_filter": SESSION_FILTERS,
}

#: Forgiveness for hand-typed / older spellings of an enum value ("the conventional", "same price").
_ALIASES: dict[str, str] = {
    "same price": "same_price",
    "sameprice": "same_price",
    "same-price": "same_price",
    "diagonal (the conventional)": "diagonal",
    "outside": "outside_rth",
    "outside rth": "outside_rth",
    "extended": "outside_rth",
    "regular": "rth",
    "cash": "rth",
    "both sides": "bid_ask",
    "total": "volume",
    "prints": "count",
}

#: The drawer's own table: one row per setting, with the plain label and the one-line meaning the
#: panel shows. `capabilities()` serves it, and it is also the payload the param registry wants.
CATALOG: tuple[dict[str, Any], ...] = (
    {"key": "cell_metric", "label": "Cell metric", "kind": "enum",
     "meaning": "What a cell is read for: both sides as shipped, one side, the row's delta, its "
                "total volume, or its print count."},
    {"key": "color_by", "label": "Colour by", "kind": "enum",
     "meaning": "How the cells are tinted: the two sides as shipped, the chosen metric, or the "
                "imbalance reading."},
    {"key": "imbalance_mode", "label": "Imbalance convention", "kind": "enum",
     "meaning": "Which comparison flags an imbalance: the row's own two sides, the diagonal against "
                "the neighbouring row, or both at once."},
    {"key": "imbalance_threshold", "label": "Ratio (same price)", "kind": "number", "unit": "x",
     "meaning": "How many times the smaller side the heavier side must carry on one row."},
    {"key": "diagonal_ratio", "label": "Ratio (diagonal)", "kind": "number", "unit": "x",
     "meaning": "The same ratio for the diagonal reading: a row's ask measured against the bid one "
                "row below."},
    {"key": "stack_min_levels", "label": "Rows for a stack", "kind": "number", "unit": "rows",
     "meaning": "How many imbalanced rows in a row in one direction make a stack — prices defended "
                "level after level."},
    {"key": "diagonal_stack_min_levels", "label": "Rows for a diagonal stack", "kind": "number",
     "unit": "rows",
     "meaning": "The same count for the diagonal reading, kept separate because the two readings "
                "stack differently."},
    {"key": "min_print_size", "label": "Minimum print size", "kind": "number", "unit": "size",
     "meaning": "Prints below this are ignored while bars are built (0 keeps every print); it "
                "applies when the engine next reads its settings.", "applies": "restart"},
    {"key": "min_level_volume", "label": "Minimum row volume", "kind": "number", "unit": "size",
     "meaning": "Rows under this traded volume are not read for imbalance, stacks, POC or value "
                "area (0 reads every row)."},
    {"key": "absorption_threshold", "label": "Absorption size", "kind": "number", "unit": "x",
     "meaning": "A row this many times the bar's average row reads as absorption — size that did "
                "not move the price."},
    {"key": "absorption_max_body_pct", "label": "Absorption body limit", "kind": "number",
     "unit": "share",
     "meaning": "Absorption only counts while the bar's body stays inside this share of its range — "
                "a bar that ran did not absorb."},
    {"key": "poc_per_bar", "label": "POC on every bar", "kind": "bool",
     "meaning": "Mark each bar's point of control: the row it traded the most volume at."},
    {"key": "value_area_per_bar", "label": "Value area on every bar", "kind": "bool",
     "meaning": "Mark each bar's value area — the rows holding the chosen share of its volume."},
    {"key": "value_area_pct", "label": "Value area share", "kind": "number", "unit": "share",
     "meaning": "The share of a bar's volume its value area holds; the usual reading is 0.70."},
    {"key": "ticks_per_row", "label": "Ticks per row", "kind": "number", "unit": "ticks",
     "meaning": "Cluster this many ticks into one row before the reading, for coarser bars "
                "(1 = one row per price)."},
    {"key": "session_filter", "label": "Session filter", "kind": "enum",
     "meaning": "Which bars the marks are drawn on: every bar, only bars inside the session window, "
                "or only bars outside it."},
    {"key": "session_start_min", "label": "Session start", "kind": "number", "unit": "min",
     "meaning": "Where the session window starts, in minutes from midnight UTC (810 = 13:30 UTC, "
                "the US cash open)."},
    {"key": "session_end_min", "label": "Session end", "kind": "number", "unit": "min",
     "meaning": "Where it ends (1200 = 20:00 UTC). A window that ends before it starts wraps past "
                "midnight."},
    {"key": "equal_tolerance", "label": "Equal tolerance", "kind": "number", "unit": "share",
     "meaning": "A row whose two sides differ by less than this share of its size reads as equal "
                "(0 needs them exactly equal)."},
    {"key": "show_equal", "label": "Mark equal rows", "kind": "bool",
     "meaning": "Outline the rows where the two sides are (near) equal — the balance rows."},
    {"key": "show_extremes", "label": "Mark extreme rows", "kind": "bool",
     "meaning": "Outline the bar's heaviest bid row and its heaviest ask row."},
)

#: The sentences the panel prints, in one place so the drawer and the routes cannot word the same
#: state two ways.
REFUSAL_NO_ROWS = "no price rows to read — this bar has nothing traded in it yet."
REFUSAL_ALL_FILTERED = "every row is under the row-volume filter — lower it to read this bar."
REFUSAL_SESSION = ("this bar is not in the window the session filter keeps — every bar is marked "
                   "when the filter is set to all.")
REFUSAL_COUNT = ("these bars carry no print counts — the count metric has nothing to read until "
                 "the feed supplies them.")
REFUSAL_NO_BARS = ("no bars arrived to annotate — the panel's own banner says whether what is on "
                   "screen is live or demo.")
REFUSAL_PATCH = ("the settings patch has to be a JSON object of named settings — nothing was read.")
REFUSAL_SETTINGS_TEXT = ("the settings text could not be read as JSON — the block shown is the "
                         "default one.")


# ── coercion ────────────────────────────────────────────────────────────────────────────────────


def _number(value: Any, default: float = 0.0) -> float:
    """float(value) or the default — a malformed cell reads as the default, never as a crash."""
    if isinstance(value, bool):
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "1", "yes", "on"):
            return True
        if text in ("false", "0", "no", "off"):
            return False
    return default


def _clamped(key: str, value: Any, default: Any) -> Any:
    low, high, _step = BOUNDS[key]
    number = _number(value, float("nan"))
    if not math.isfinite(number):
        return default
    number = min(high, max(low, number))
    if key in WHOLE_KEYS:
        return int(round(number))
    return round(number, 6)


def _choice(key: str, value: Any, default: str) -> str:
    if not isinstance(value, str):
        return default
    text = value.strip().lower()
    if text in CHOICES[key]:
        return text
    text = _ALIASES.get(text, text.replace("-", "_").replace(" ", "_"))
    return text if text in CHOICES[key] else default


def clean(patch: Any) -> dict[str, Any]:
    """The settings block, coerced and clamped onto `DEFAULTS`.

    Never raises. Unknown keys are dropped; a wrong type is coerced (a number for a bool switch, a
    numeric string for a number) or falls back to the default; an out-of-range number is clamped to
    its bound. Only the feature block comes back — no other part of the config is touched, and
    nothing here reads the config store.
    """
    out = dict(DEFAULTS)
    if not isinstance(patch, Mapping):
        return out
    for key, default in DEFAULTS.items():
        if key not in patch or patch[key] is None:
            continue
        value = patch[key]
        if isinstance(default, bool):
            out[key] = _bool(value, default)
        elif key in CHOICES:
            out[key] = _choice(key, value, default)
        else:
            out[key] = _clamped(key, value, default)
    return out


def capabilities() -> list[dict[str, Any]]:
    """One row per setting: what the drawer shows, and what the param registry wants.

    `path` is the config path the parent registers, `view` the panel that shows the control, `kind`
    how to render it, and `applies` whether a save is live or has to wait for the engine to re-read
    its settings.
    """
    rows: list[dict[str, Any]] = []
    for spec in CATALOG:
        key = spec["key"]
        item: dict[str, Any] = {
            "key": key,
            "path": "atlas.footprint." + key,
            "label": spec["label"],
            "group": "Footprint",
            "view": "orderflow",
            "kind": spec["kind"],
            "unit": spec.get("unit", ""),
            "meaning": spec["meaning"],
            "applies": spec.get("applies", "live"),
            "default": DEFAULTS[key],
        }
        if spec["kind"] == "enum":
            item["choices"] = list(CHOICES[key])
        elif spec["kind"] == "number":
            low, high, step = BOUNDS[key]
            item.update({"min": low, "max": high, "step": step})
        rows.append(item)
    return rows


# ── the session window ──────────────────────────────────────────────────────────────────────────


def _epoch_ms(when: Any) -> float | None:
    """Epoch seconds or milliseconds (or an ISO stamp) to milliseconds. None when unreadable.

    The footprint payload carries `time` in seconds; a caller with milliseconds (the engine's own
    stamps) passes those, so both are accepted and told apart by magnitude.
    """
    if isinstance(when, bool):
        return None
    if isinstance(when, str):
        text = when.strip()
        if not text:
            return None
        # §148 T6-F7: the panel reads the same text with `Date.parse`, so the shape accepted here
        # is the shape both engines read: an ISO date and time joined by `T`, a missing zone
        # meaning UTC. `fromisoformat` alone also takes the basic `20260918` form and the space
        # separator, which `Date.parse` answers NaN for — a bar whose clock the two engines read
        # differently is a bar neither should filter on, so the narrow shapes are refused.
        if "T" not in text.upper():
            return None
        try:                                       # ISO stamp with or without a timezone
            stamp = _dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=_dt.timezone.utc)
        return stamp.timestamp() * 1000.0
    number = _number(when, float("nan"))
    if not math.isfinite(number):
        return None
    return number * 1000.0 if abs(number) < 1e11 else number


def session_verdict(when: Any, settings: Any = None) -> str:
    """``in`` | ``out`` | ``all`` — is this bar inside the session window the filter keeps?

    The window is two clock times in UTC minutes from midnight; a window that ends before it starts
    wraps past midnight, and start == end means the whole day (so a 24 h instrument is never
    filtered). An unreadable stamp is ``all``: a bar whose clock is unknown is not thrown away.
    """
    cfg = clean(settings)
    mode = cfg["session_filter"]
    if mode == "all":
        return "all"
    stamp = _epoch_ms(when)
    if stamp is None:
        return "all"
    moment = _dt.datetime.fromtimestamp(stamp / 1000.0, tz=_dt.timezone.utc)
    minute = moment.hour * 60 + moment.minute
    start, end = int(cfg["session_start_min"]), int(cfg["session_end_min"])
    if start == end:
        return "in" if mode == "rth" else "out"
    inside = (start <= minute < end) if start < end else (minute >= start or minute < end)
    if mode == "rth":
        return "in" if inside else "out"
    return "out" if inside else "in"


# ── the rows ────────────────────────────────────────────────────────────────────────────────────


def _rows(raw: Any) -> list[dict[str, Any]]:
    """Usable price rows, sorted by price. Anything unreadable is dropped, never guessed.

    Accepts a list of dicts (``price``/``bid``/``ask``/``volume``/``delta``/``count``) or a
    price -> (bid, ask) mapping, which is the shape `analytics/footprint.py` already works on. A
    row with no readable price is not a row; `volume` defaults to the two sides summed and `delta`
    to ask minus bid, and a missing `count` stays None (it is never invented).
    """
    items: Any = raw
    if isinstance(raw, Mapping):
        items = []
        for price, side in raw.items():
            if isinstance(side, (list, tuple)):
                pair = list(side) + [0.0, 0.0]
                items.append({"price": price, "bid": pair[0], "ask": pair[1]})
            else:
                items.append({"price": price, "bid": side, "ask": 0.0})
    if not isinstance(items, (list, tuple)):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        price = _number(item.get("price"), float("nan"))
        if not math.isfinite(price):
            continue
        bid = max(0.0, _number(item.get("bid")))
        ask = max(0.0, _number(item.get("ask")))
        volume = _number(item.get("volume"), -1.0)
        count = _number(item.get("count"), -1.0)
        delta = _number(item.get("delta"), ask - bid)
        out.append({
            "price": price,
            "bid": bid,
            "ask": ask,
            "volume": (bid + ask) if volume < 0 else max(0.0, volume),
            "count": count if count >= 0 else None,
            "delta": delta,
        })
    out.sort(key=lambda row: row["price"])
    return out


def row_step(prices: Sequence[float], tick_size: float = 0.0, ticks_per_row: int = 1) -> float:
    """The price step one row covers: the instrument's tick (or the smallest gap the rows show)
    times the cluster width. 0 means no step could be read at all (a single row)."""
    tick = abs(_number(tick_size))
    if tick <= 0:
        gaps = [b - a for a, b in zip(prices, prices[1:]) if b - a > 1e-12]
        tick = min(gaps) if gaps else 0.0
    if tick <= 0:
        return 0.0
    return tick * max(1, int(ticks_per_row))


def _clustered(raw: list[dict[str, Any]], cfg: dict[str, Any],
               tick_size: float) -> tuple[list[dict[str, Any]], float]:
    """The rows the reading works on, with `ticks_per_row` ticks merged into one row.

    With `ticks_per_row` 1 (the default) every level stays its own row, so a mark lands exactly on
    the cell the chart drew. Above 1, a row carries its span (the prices the cluster covers), its
    member count and the summed sides, and the drawer's marks draw over that span.
    """
    step = row_step([row["price"] for row in raw], tick_size, int(cfg["ticks_per_row"]))
    if int(cfg["ticks_per_row"]) <= 1 or step <= 0 or not raw:
        return [dict(row, span=[row["price"], row["price"]], levels=1) for row in raw], step
    buckets: dict[int, list[dict[str, Any]]] = {}
    for row in raw:
        # Floor, not round: a tick on the cluster boundary belongs to the row it opens (100.25 on a
        # 0.25 tick with two ticks per row opens [100.25, 100.5]) — and rounding a .5 key splits the
        # cluster in half, which is how the count metric lost half its prints to a phantom row.
        buckets.setdefault(int(math.floor(row["price"] / step + 1e-9)), []).append(row)
    out: list[dict[str, Any]] = []
    for key in sorted(buckets):
        group = sorted(buckets[key], key=lambda row: row["price"])
        counts = [member["count"] for member in group]
        out.append({
            "price": group[0]["price"],
            "span": [group[0]["price"], group[-1]["price"]],
            "levels": len(group),
            "bid": sum(member["bid"] for member in group),
            "ask": sum(member["ask"] for member in group),
            "volume": sum(member["volume"] for member in group),
            "delta": sum(member["delta"] for member in group),
            "count": sum(counts) if counts and all(c is not None for c in counts) else None,
        })
    return out, step


def metric_value(row: Mapping[str, Any], metric: str) -> float | None:
    """The number a cell is read for. None when the row cannot answer (counts the feed did not send)."""
    if metric == "bid":
        return _number(row.get("bid"))
    if metric == "ask":
        return _number(row.get("ask"))
    if metric == "delta":
        return _number(row.get("ask")) - _number(row.get("bid"))
    if metric == "count":
        count = row.get("count")
        return None if count is None else _number(count)
    return _number(row.get("bid")) + _number(row.get("ask"))       # bid_ask and volume


def _reading(bid: float, ask: float, bid_cmp: float, ask_cmp: float,
             threshold: float) -> tuple[str | None, float | None]:
    """One row's imbalance reading: the side that carried the size, and its ratio.

    The ask side is aggression against the offer (a "buy" imbalance); the bid side is aggression
    into the bid (a "sell" one). A comparison side at zero is an imbalance by itself — there was
    nothing on the other side to compare with — and an empty row is neither side.
    """
    if ask > 0 and (bid_cmp <= 0 or ask / max(bid_cmp, 1e-12) >= threshold):
        return "buy", (round(ask / bid_cmp, 4) if bid_cmp > 0 else None)
    if bid > 0 and (ask_cmp <= 0 or bid / max(ask_cmp, 1e-12) >= threshold):
        return "sell", (round(bid / ask_cmp, 4) if ask_cmp > 0 else None)
    return None, None


def _ladder_key(price: float, step: float) -> int:
    """The step-count a price lands on — half-UP, exactly as the panel's ``Math.round`` keys it.

    Python's own ``round`` is half-to-even, so a price sitting exactly half a step up keys one row
    lower than the panel keys it (22 of 240 half-step fuzz cases disagreed) and the two halves of
    the diagonal reading then point at different neighbours (T6-F06).
    """
    return int(math.floor(price / step + 0.5))


def _readings(rows: list[dict[str, Any]], step: float, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Both conventions for every row: same-price against its own sides, diagonal against the
    neighbouring rows (the convention `analytics/footprint.py` documents and prints)."""
    ladder = {_ladder_key(row["price"], step): row for row in rows} if step > 0 else {}
    out: list[dict[str, Any]] = []
    for row in rows:
        same_side, same_ratio = _reading(row["bid"], row["ask"], row["bid"], row["ask"],
                                         float(cfg["imbalance_threshold"]))
        if ladder:
            key = _ladder_key(row["price"], step)
            below = ladder.get(key - 1)
            above = ladder.get(key + 1)
            bid_cmp = below["bid"] if below is not None else row["bid"]
            ask_cmp = above["ask"] if above is not None else row["ask"]
        else:
            bid_cmp, ask_cmp = row["bid"], row["ask"]
        diag_side, diag_ratio = _reading(row["bid"], row["ask"], bid_cmp, ask_cmp,
                                         float(cfg["diagonal_ratio"]))
        out.append({
            "same_price": {"side": same_side, "ratio": same_ratio, "mode": "same_price"},
            "diagonal": {"side": diag_side, "ratio": diag_ratio, "mode": "diagonal"},
        })
    return out


def _primary(readings: Mapping[str, Any], mode: str) -> Mapping[str, Any] | None:
    """Which reading the row wears as its mark. `both` shows the same-price one where it exists and
    the diagonal one where it does not, so no row is silently unmarked."""
    if mode == "diagonal":
        return readings["diagonal"]
    if mode == "both":
        chosen = readings["same_price"]
        return chosen if chosen["side"] else readings["diagonal"]
    return readings["same_price"]


def _runs(rows: list[dict[str, Any]], sides: list[str | None], modes: list[str], step: float,
          min_levels: int) -> list[dict[str, Any]]:
    """Consecutive imbalanced rows in one direction, on adjacent rows only.

    A row with no mark breaks the run, and so does a gap in price: a stack is prices defended level
    after level, so a missing row between two marked ones is not the same stack (the same reading
    `atlas/imbalance.py` builds for the ladder). A run wears the convention of the row that
    opened it — under `both` a run is same-price rows or diagonal rows, never a blend.
    """
    runs: list[dict[str, Any]] = []
    current: list[int] = []
    tolerance = max(step * 1e-6, 1e-9)

    def flush() -> None:
        if len(current) >= min_levels and sides[current[0]]:
            block = [rows[i] for i in current]
            ratios = [r for r in (block[i].get("_ratio") for i in range(len(block))) if r]
            runs.append({
                "mode": modes[current[0]],
                "side": sides[current[0]],
                "from_price": max(row["price"] for row in block),
                "to_price": min(row["price"] for row in block),
                "levels": len(block),
                "volume": round(sum(row["volume"] for row in block), 6),
                "max_ratio": round(max(ratios), 4) if ratios else None,
            })
        current.clear()

    for index, row in enumerate(rows):
        side = sides[index]
        if side is None:
            flush()
            continue
        if current:
            previous = rows[current[-1]]
            adjacent = (abs((row["price"] - previous["price"]) - step) <= tolerance) if step > 0 else False
            if sides[current[-1]] != side or not adjacent:
                flush()
        current.append(index)
    flush()
    return runs


def annotate_bar(levels: Any, settings: Any = None, *, bar: Any = None,
                 tick_size: float = 0.0) -> dict[str, Any]:
    """One bar's marks: every row annotated, plus the POC, the value area, the stacks and the
    absorption rows.

    `levels` is the bar's price rows (list of dicts, or a price -> (bid, ask) mapping); `bar` is the
    bar itself when it carries OHLC (`open`/`high`/`low`/`close`, used by the absorption body test)
    and a `time` (used by the session filter). A bar with nothing readable answers `ok: false` and
    one plain sentence instead of a fabricated cell.
    """
    cfg = clean(settings)
    raw = _rows(levels)
    rows, step = _clustered(raw, cfg, tick_size)

    block: dict[str, Any] = {
        "ok": True, "metric": cfg["cell_metric"], "color_by": cfg["color_by"],
        "rows": [], "poc": None, "value_area": None, "stacks": [], "absorption": [],
        "extremes": {"max_bid": None, "max_ask": None},
        "counts": {"rows": 0, "imbalance_buy": 0, "imbalance_sell": 0, "stacks": 0, "diagonal": 0,
                   "absorption": 0, "equal": 0},
        "filtered": {"levels": 0, "volume": 0.0},
        "session": "all", "refusal": None, "settings": cfg, "body_known": False,
    }

    verdict = session_verdict((bar or {}).get("time") if isinstance(bar, Mapping) else None, cfg)
    block["session"] = verdict
    if verdict == "out":
        block["ok"] = False
        block["refusal"] = REFUSAL_SESSION
        return block

    keep = [row for row in rows if row["volume"] >= cfg["min_level_volume"]]
    dropped = [row for row in rows if row["volume"] < cfg["min_level_volume"]]
    block["filtered"] = {"levels": len(dropped),
                         "volume": round(sum(row["volume"] for row in dropped), 6)}
    if not keep:
        block["ok"] = False
        block["refusal"] = REFUSAL_ALL_FILTERED if rows else REFUSAL_NO_ROWS
        return block

    total = sum(row["volume"] for row in keep)
    readings = _readings(keep, step, cfg)
    mode = cfg["imbalance_mode"]

    # The active reading, then the stacks of both conventions: a user who marks both wants the
    # stacks of both, not just the convention that happens to be primary.
    primary = [_primary(pair, mode) for pair in readings]
    stacks = _runs([dict(row, _ratio=pair["ratio"]) for row, pair in zip(keep, primary)],
                   [pair["side"] for pair in primary],
                   [pair["mode"] for pair in primary], step, int(cfg["stack_min_levels"]))
    if mode == "both":
        stacks += _runs([dict(row, _ratio=pair["diagonal"]["ratio"]) for row, pair in zip(keep, readings)],
                        [pair["diagonal"]["side"] for pair in readings],
                        ["diagonal"] * len(readings), step, int(cfg["diagonal_stack_min_levels"]))
    stacked: dict[int, dict[str, Any]] = {}
    for run in stacks:
        for index, row in enumerate(keep):
            if run["to_price"] <= row["price"] <= run["from_price"]:
                stacked[index] = {"mode": run["mode"], "side": run["side"], "levels": run["levels"],
                                  "max_ratio": run["max_ratio"]}

    # Absorption: the row is big against the bar's average row, and the bar's body stayed inside its
    # range (`desktop/ui`'s footprint renderer uses the same two clauses).
    average = total / len(keep)
    body_known = False
    body_ok = True
    if isinstance(bar, Mapping):
        numbers = [_number(bar.get(field), float("nan")) for field in ("open", "high", "low", "close")]
        if all(math.isfinite(value) for value in numbers):
            body_known = True
            opened, high, low, closed = numbers
            body_ok = abs(closed - opened) < (high - low) * float(cfg["absorption_max_body_pct"])
    absorbed: dict[int, dict[str, Any]] = {}
    for index, row in enumerate(keep):
        ratio = (row["volume"] / average) if average > 0 else 0.0
        if body_ok and ratio >= float(cfg["absorption_threshold"]):
            absorbed[index] = {"price": row["price"], "volume": round(row["volume"], 6),
                               "ratio": round(ratio, 4)}

    # POC and value area, both on total traded volume: the row that traded the most, with the lower
    # price winning a tie (the tie-break `calc.poc` uses), then the value area expanded from it.
    by_volume = sorted(range(len(keep)), key=lambda i: (keep[i]["volume"], -keep[i]["price"]))
    poc_index = by_volume[-1]
    poc_row = keep[poc_index]
    poc = {
        "price": round(poc_row["price"], 10),
        "volume": round(poc_row["volume"], 6),
        "share_pct": round((poc_row["volume"] / total) * 100, 4) if total else 0.0,
        "metric": metric_value(poc_row, cfg["cell_metric"]),
        "row": poc_index,
    } if cfg["poc_per_bar"] else None

    area: dict[str, Any] | None = None
    area_range = (poc_index, poc_index)
    if cfg["value_area_per_bar"]:
        target = total * float(cfg["value_area_pct"])
        accumulated = poc_row["volume"]
        low_index = high_index = poc_index
        while accumulated < target and (low_index > 0 or high_index < len(keep) - 1):
            up = keep[high_index + 1]["volume"] if high_index + 1 < len(keep) else -1.0
            down = keep[low_index - 1]["volume"] if low_index - 1 >= 0 else -1.0
            if up >= down:
                high_index += 1
                accumulated += up
            else:
                low_index -= 1
                accumulated += down
        area_range = (low_index, high_index)
        area = {
            "val": round(keep[low_index]["price"], 10),
            "vah": round(keep[high_index]["price"], 10),
            "pct": float(cfg["value_area_pct"]),
            "rows": high_index - low_index + 1,
            "share_pct": round((accumulated / total) * 100, 4) if total else 0.0,
        }

    tolerance = float(cfg["equal_tolerance"])
    annotated: list[dict[str, Any]] = []
    for index, row in enumerate(keep):
        pair = primary[index]
        read = metric_value(row, cfg["cell_metric"])
        equal = (abs(row["bid"] - row["ask"]) <= tolerance * (row["bid"] + row["ask"])
                 if tolerance > 1e-9 else (row["bid"] > 0 and row["bid"] == row["ask"]))
        annotated.append({
            "price": round(row["price"], 10),
            "span": [round(row["span"][0], 10), round(row["span"][1], 10)],
            "levels": int(row["levels"]),
            "bid": round(row["bid"], 6),
            "ask": round(row["ask"], 6),
            "volume": round(row["volume"], 6),
            "delta": round(row["delta"], 6),
            "count": None if row["count"] is None else round(row["count"], 6),
            "metric": None if read is None else round(read, 6),
            "imbalance": pair["side"],
            "imbalance_mode": pair["mode"] if pair["side"] else None,
            "imbalance_ratio": pair["ratio"],
            "readings": {name: readings[index][name]["side"] for name in ("same_price", "diagonal")},
            "ratios": {name: readings[index][name]["ratio"] for name in ("same_price", "diagonal")},
            "stack": stacked.get(index),
            "absorption": index in absorbed,
            "equal": bool(cfg["show_equal"] and equal),
            "poc": bool(cfg["poc_per_bar"] and index == poc_index),
            "value_area": bool(cfg["value_area_per_bar"] and area_range[0] <= index <= area_range[1]),
        })

    extremes: dict[str, Any] = {"max_bid": None, "max_ask": None}
    if cfg["show_extremes"]:
        heaviest_bid = max(range(len(keep)), key=lambda i: keep[i]["bid"])
        heaviest_ask = max(range(len(keep)), key=lambda i: keep[i]["ask"])
        if keep[heaviest_bid]["bid"] > 0:
            extremes["max_bid"] = round(keep[heaviest_bid]["price"], 10)
            annotated[heaviest_bid]["extreme"] = "bid"
        if keep[heaviest_ask]["ask"] > 0:
            extremes["max_ask"] = round(keep[heaviest_ask]["price"], 10)
            annotated[heaviest_ask]["extreme"] = "ask"

    refusals = []
    if cfg["cell_metric"] == "count" and any(row["count"] is None for row in keep):
        refusals.append(REFUSAL_COUNT)
    if refusals:
        # A bar whose cell metric cannot be read is not a bar to mark: the block refuses as a whole,
        # the way the session filter and the row filter refuse, so nothing is drawn from it.
        block["ok"] = False

    block.update({
        "rows": annotated,
        "poc": poc,
        "value_area": area,
        "stacks": stacks,
        "absorption": sorted(absorbed.values(), key=lambda item: -item["volume"]),
        "extremes": extremes,
        "counts": {
            "rows": len(annotated),
            "imbalance_buy": sum(1 for pair in primary if pair["side"] == "buy"),
            "imbalance_sell": sum(1 for pair in primary if pair["side"] == "sell"),
            "stacks": len(stacks),
            "diagonal": sum(1 for pair in readings if pair["diagonal"]["side"]),
            "absorption": len(absorbed),
            "equal": sum(1 for row in annotated if row["equal"]),
        },
        "body_known": body_known,
        "refusal": refusals[0] if refusals else None,
    })
    return block


def annotate_bars(bars: Any, settings: Any = None, *, tick_size: float = 0.0) -> dict[str, Any]:
    """Every bar in a footprint payload annotated, with what was kept and what was not.

    A bar the session filter keeps out answers `ok: false` with the session sentence, so the panel
    draws nothing on it rather than a mark the filter excluded.
    """
    cfg = clean(settings)
    blocks: list[dict[str, Any]] = []
    if isinstance(bars, (list, tuple)):
        for item in bars:
            if not isinstance(item, Mapping):
                continue
            blocks.append(annotate_bar(item.get("levels"), cfg, bar=item, tick_size=tick_size))
    kept = sum(1 for block in blocks if block["ok"])
    return {
        "ok": bool(blocks) and kept > 0,
        "bars": blocks,
        "kept": kept,
        "skipped": len(blocks) - kept,
        "metric": cfg["cell_metric"],
        "settings": cfg,
        "refusal": None if blocks and kept else REFUSAL_NO_BARS,
    }


# ── routes ──────────────────────────────────────────────────────────────────────────────────────


def _decode_settings(raw: Any) -> tuple[Any, str | None]:
    """The `settings=` query text as a patch, plus a sentence when it could not be read."""
    if raw is None or not str(raw).strip():
        return None, None
    try:
        return json.loads(str(raw)), None
    except (TypeError, ValueError):
        return None, REFUSAL_SETTINGS_TEXT


@router.get("/footprint/config")
async def footprint_config(
    settings: str | None = Query(
        default=None,
        description="The stored block as JSON text, validated and echoed back (optional)."),
) -> dict[str, Any]:
    """The footprint settings block, its defaults, and every control the drawer may show.

    Read-only: the block that comes back is `clean()` of the stored block the caller passes in (or
    of the defaults when it passes none), which is exactly what the drawer renders. Nothing here
    writes the config — a GET never does.
    """
    supplied, note = _decode_settings(settings)
    return {
        "ok": True,
        "block": clean(supplied),
        "defaults": dict(DEFAULTS),
        "capabilities": capabilities(),
        "source": "supplied" if supplied is not None else "defaults",
        "detail": note,
    }


@router.post("/footprint/config")
async def footprint_config_save(patch: Any = Body(default=None)) -> dict[str, Any]:
    """Validate + clamp a patch and hand back the block that was accepted.

    The store owns persistence (the panel writes the accepted block back through the control API);
    this route is the validation half, so a control can never save a value the panel cannot draw.
    A body that is not a JSON object is refused with one sentence rather than read as "nothing".
    """
    if patch is not None and not isinstance(patch, Mapping):
        return {"ok": False, "detail": REFUSAL_PATCH, "block": clean(None),
                "defaults": dict(DEFAULTS), "capabilities": capabilities()}
    block = clean(patch)
    return {
        "ok": True,
        "block": block,
        "defaults": dict(DEFAULTS),
        "capabilities": capabilities(),
        "changed": [key for key in DEFAULTS if block[key] != DEFAULTS[key]],
        "detail": "the block is valid; the config store keeps it.",
    }
