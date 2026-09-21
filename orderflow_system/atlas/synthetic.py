"""
Synthetic instruments — ratios, spreads, baskets and basis series built from this build's own legs.

P1-6 of the competitive audit: the reference platform's synthetic-symbol and spread builder is a
paid-tier feature its buyers name, and the question behind it is always the same — no single
instrument answers "what is the perp doing against spot", "how rich is ETH against BTC" or "is the
majors complex bid or offered". All three are arithmetic over series this build already stores, so
this layer needs no new venue and no new feed.

A LEG is {symbol, side, weight}: side +1 adds the leg, -1 subtracts it, weight scales it. Series
arrive as plain {ts_ms, price} rows — the router reads them from the stored 1-minute candles
(`candles`, the table the engine writes on every candle close) and this module only ever does
arithmetic on what it is handed, so it is testable offline and works in replay.

KINDS (`plus` = the weighted +1 legs, `minus` = the weighted -1 legs):

  ratio   plus / minus                   a relative value — ETH/BTC, SOL/ETH, cross-venue pairs
  basis   (plus - minus) / minus         a premium as a fraction of the leg it is measured against
  spread  plus - minus                   a difference in the quote currency
  basket  (plus - minus) / sum(weights)  a weighted average price for a group

ratio, basis and spread need a leg on each side; a basket needs at least one leg and can be
one-sided. Every definition keeps a stable id (a slug of its name), so a stored definition and a
submitted one with the same name are the same instrument.

ALIGNMENT: the legs' own rows are bucketed to `align_ms` (the last print in a bucket is that
bucket's price — the rule the correlation tracker uses), the union of those buckets is the
composite's timeline, and a leg with no print in a bucket is carried at its last price — but only
while the gap is within `max_gap_ms`, and never backwards past its first print. A bucket where a leg
has nothing to carry is dropped rather than answered with a stale or invented price, and how much of
each leg was carried rides out as `carried_pct`: a basket that is 40% carried prices is a different
statement from one that printed every bucket.

WHAT IS REPORTED: the composite series, the legs' correlation, the current spread in absolute and
bps terms, the z-score of the composite over the window, the share of the window it spent beyond
`z_stretch` sigma, and a plain sentence — "BTC perp is trading 14.2 bps over spot — 1.4 sigma rich
over the last 4 hours".
"""

from __future__ import annotations

import math
import re
import time
from copy import deepcopy
from typing import Any, Optional, Sequence

from fastapi import APIRouter, Body, Query

#: The router the launcher includes; declared here so the pure half above stays importable on its
#: own and the route table of this module is visible to the end-of-build audit.
router = APIRouter(prefix="/api/atlas", tags=["atlas"])

KINDS: tuple[str, ...] = ("ratio", "spread", "basket", "basis")

#: Kinds that are meaningless without one leg on each side.
BOTH_SIDES: tuple[str, ...] = ("ratio", "spread", "basis")

#: What one composite value is, per kind — read by the payload, never guessed by the panel.
VALUE_UNIT = {"ratio": "ratio", "basis": "fraction", "spread": "price", "basket": "price"}

#: Side words a submitted leg may use instead of +1/-1.
SIDE_WORDS = {
    "long": 1, "buy": 1, "bid": 1, "plus": 1, "+": 1, "1": 1, "1.0": 1,
    "short": -1, "sell": -1, "ask": -1, "minus": -1, "-": -1, "-1": -1, "-1.0": -1,
}

#: The definitions this build ships with. Every one is copyable and editable in the panel; the
#: perp-vs-spot basis names the leg it cannot read instead of drawing a line through nothing.
STARTERS: list[dict[str, Any]] = [
    {
        "id": "eth-btc-ratio", "name": "ETH/BTC ratio", "kind": "ratio",
        "legs": [{"symbol": "ETHUSDT", "side": 1, "weight": 1.0},
                 {"symbol": "BTCUSDT", "side": -1, "weight": 1.0}],
        "note": "How much BTC one ETH is worth — the relative-value read the majors trade on.",
    },
    {
        "id": "majors-basket", "name": "Majors basket", "kind": "basket",
        "legs": [{"symbol": "BTCUSDT", "side": 1, "weight": 0.5},
                 {"symbol": "ETHUSDT", "side": 1, "weight": 0.3},
                 {"symbol": "SOLUSDT", "side": 1, "weight": 0.2}],
        "note": "A weighted average of the majors — one line for the complex instead of three.",
    },
    {
        "id": "btc-perp-basis", "name": "BTC perp basis", "kind": "basis",
        "legs": [{"symbol": "BTCUSDT", "side": 1, "weight": 1.0},
                 {"symbol": "BTCUSD", "side": -1, "weight": 1.0}],
        "note": "Perp against spot. Point the second leg at whatever BTC spot series you stream "
                "(BTC/USD from Alpaca, BTCUSDm from MT5) — until that leg has stored history the "
                "panel names it instead of drawing a line.",
    },
]

STARTER_IDS: tuple[str, ...] = tuple(str(d.get("id")) for d in STARTERS)

DEFAULTS: dict[str, Any] = {
    "window_min": 240,        # how much history a composite is built from (4 h)
    "align_ms": 60_000,       # the grid the legs are unioned onto (the stored candle timeframe)
    "max_gap_ms": 300_000,    # a leg silent longer than this is not carried (0 = carry anything)
    "min_samples": 10,        # below this many aligned points no z-score is reported
    "z_stretch": 1.0,         # the sigma band the "share of the window beyond" figure counts
    "max_points": 600,        # chart points one compose answers with
    "refresh_ms": 20_000,     # the panel's own cadence
    "definitions": STARTERS,  # deep-copied on every read; never mutated in place
}

MAX_LEGS = 8
#: How many definitions the config block keeps. A 25th save used to drop the oldest while the route
#: answered `"saved": true` (§148 T4-F8); it is refused with a sentence the panel prints instead.
MAX_DEFINITIONS = 24
_WINDOW_BOUNDS = (10, 10_080)          # 10 minutes .. 7 days
_ALIGN_BOUNDS = (15_000, 3_600_000)    # 15 s .. 1 h
_GAP_BOUNDS = (0, 86_400_000)          # 0 = carry anything, up to a day
_SAMPLES_BOUNDS = (3, 500)
_STRETCH_BOUNDS = (0.25, 4.0)
_POINTS_BOUNDS = (30, 2_000)
_REFRESH_BOUNDS = (2_000, 600_000)

#: The panel's own maximum for a leg weight (synthetic.js's `max="1000"`). An unbounded weight
#: is not cosmetic: `compose` squares the weighted values, so a 1e300 leg overflowed the
#: arithmetic and the compose route answered 500 while its own docstring promises "never a 500".
LEG_WEIGHT_MAX = 1000.0


# ── coercion ────────────────────────────────────────────────────────────────

def _num(value: Any) -> Optional[float]:
    """A finite float, or None — bools are not numbers here."""
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _clamp(value: Any, lo: float, hi: float, default: float) -> float:
    got = _num(value)
    if got is None:
        return float(default)
    return min(float(hi), max(float(lo), got))


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(text: Any, fallback: str = "synthetic") -> str:
    """A stable id from a name: lowercase [a-z0-9-], never empty, never longer than 48."""
    out = _SLUG_RE.sub("-", str(text or "").strip().lower()).strip("-")[:48]
    return out or fallback


def _clean_note(raw: Any) -> str:
    return str(raw or "").strip()[:400]


def normalise_leg(raw: Any) -> Optional[dict[str, Any]]:
    """One leg from whatever shape it arrived in.

    Accepts {"symbol", "side", "weight"}, a bare symbol string, or a (symbol, side[, weight]) pair.
    Returns None only when the leg names no instrument at all: a weight that is zero, negative or
    unreadable survives this call — unreadable ones as 0.0 — so the validator can refuse it by name
    rather than silently dropping the leg behind the user's back. A weight above the panel's own
    maximum (LEG_WEIGHT_MAX) is clamped to it: the panel cannot author one, and an unbounded weight
    overflowed the composite's arithmetic.
    """
    if isinstance(raw, str):
        raw = {"symbol": raw}
    elif isinstance(raw, (list, tuple)) and raw:
        raw = {"symbol": raw[0], "side": raw[1] if len(raw) > 1 else 1,
               "weight": raw[2] if len(raw) > 2 else 1.0}
    if not isinstance(raw, dict):
        return None
    symbol = str(raw.get("symbol") or "").strip().upper()[:32]
    if not symbol:
        return None
    side_raw = raw.get("side", 1)
    if isinstance(side_raw, str):
        side = SIDE_WORDS.get(side_raw.strip().lower(), 0)
    else:
        number = _num(side_raw)
        side = 0 if number == 0 else (-1 if number is not None and number < 0 else 1)
    if side not in (1, -1):
        return None
    weight = _num(raw.get("weight")) if "weight" in raw else 1.0
    if "weight" in raw and weight is None:
        weight = 0.0                     # unreadable weight: the validator names it
    if weight is None:
        weight = 1.0
    weight = min(LEG_WEIGHT_MAX, weight)     # the panel's cap; an unbounded weight 500ed compose
    return {"symbol": symbol, "side": int(side), "weight": float(weight)}


def clean_definition(raw: Any, *, fallback_id: str = "") -> Optional[dict[str, Any]]:
    """A definition coerced onto the canonical shape, or None when nothing usable is left.

    Never raises. Unknown kind, a missing name, no leg with a positive weight, or a ratio/spread/
    basis with only one side all come back as None. Keeps one leg per instrument, keeps a stable id
    (the submitted one, else a slug of the name), and drops anything it could not read.
    """
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or "").strip().lower()
    if kind not in KINDS:
        return None
    name = str(raw.get("name") or "").strip()[:60]
    if not name:
        return None
    raw_legs = raw.get("legs")
    legs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in (raw_legs if isinstance(raw_legs, (list, tuple)) else []):
        leg = normalise_leg(item)
        if leg is None or leg["weight"] <= 0 or leg["symbol"] in seen:
            continue
        seen.add(leg["symbol"])
        legs.append(leg)
        if len(legs) >= MAX_LEGS:
            break
    if not legs:
        return None
    if kind in BOTH_SIDES and not (any(leg["side"] > 0 for leg in legs)
                                   and any(leg["side"] < 0 for leg in legs)):
        return None
    out: dict[str, Any] = {"id": slug(raw.get("id") or fallback_id or name), "name": name,
                           "kind": kind, "legs": legs}
    note = _clean_note(raw.get("note"))
    if note:
        out["note"] = note
    if raw.get("builtin") is True:
        out["builtin"] = True
    return out


def check_definition(raw: Any) -> tuple[Optional[dict[str, Any]], list[str]]:
    """Validate one submitted definition.

    Returns (definition, problems). `problems` are plain sentences meant for the user and empty
    when the definition was accepted; a rejected definition comes back as None. This is the strict
    half — clean_definition() repairs what it can, this one says what is wrong instead.
    """
    problems: list[str] = []
    if not isinstance(raw, dict):
        return None, ["a synthetic instrument is an object with a name, a kind and at least one leg"]
    name = str(raw.get("name") or "").strip()
    if not name:
        problems.append("give it a name — that is what the panel and the read sentence call it")
    kind = str(raw.get("kind") or "").strip().lower()
    if kind not in KINDS:
        problems.append(f"kind must be one of {' | '.join(KINDS)} (got {kind or 'nothing'})")
    raw_legs = raw.get("legs")
    legs: list[dict[str, Any]] = []
    if not isinstance(raw_legs, (list, tuple)) or not raw_legs:
        problems.append("add at least one leg — a synthetic instrument is nothing without a leg")
    else:
        if len(raw_legs) > MAX_LEGS:
            problems.append(f"at most {MAX_LEGS} legs — a composite of more than that is a portfolio, "
                            "not a spread")
        for index, item in enumerate(list(raw_legs)[:MAX_LEGS]):
            leg = normalise_leg(item)
            if leg is None:
                problems.append(f"leg {index + 1} names no instrument")
                continue
            if any(existing["symbol"] == leg["symbol"] for existing in legs):
                problems.append(f"{leg['symbol']} is listed twice — give each leg a different "
                                "instrument")
                continue
            if leg["weight"] <= 0:
                problems.append(f"{leg['symbol']}'s weight is {leg['weight']:g} — every leg needs a "
                                "weight above 0")
                continue
            legs.append(leg)
    if kind in BOTH_SIDES and legs:
        sides = {leg["side"] for leg in legs}
        if sides != {1, -1}:
            problems.append(f"a {kind} needs a leg on each side — one added and one subtracted")
    if problems:
        return None, problems
    definition = clean_definition({"id": raw.get("id"), "name": name, "kind": kind, "legs": legs,
                                   "note": raw.get("note")})
    if definition is None:
        return None, ["that definition could not be read — check the name, the kind and the legs"]
    return definition, []


def clean(patch: Any) -> dict[str, Any]:
    """Coerce/clamp an incoming settings patch onto DEFAULTS. Never raises.

    Unknown keys are dropped, wrong types are defaulted, and every bound is the same one the panel
    prints. An empty or unreadable `definitions` list falls back to the starters — a hand-edited
    config cannot leave the panel with nothing to compose.
    """
    out = deepcopy(DEFAULTS)
    out["definitions"] = deepcopy(STARTERS)
    if not isinstance(patch, dict):
        return out
    out["window_min"] = int(_clamp(patch.get("window_min"), *_WINDOW_BOUNDS, DEFAULTS["window_min"]))
    out["align_ms"] = int(_clamp(patch.get("align_ms"), *_ALIGN_BOUNDS, DEFAULTS["align_ms"]))
    out["max_gap_ms"] = int(_clamp(patch.get("max_gap_ms"), *_GAP_BOUNDS, DEFAULTS["max_gap_ms"]))
    out["min_samples"] = int(_clamp(patch.get("min_samples"), *_SAMPLES_BOUNDS, DEFAULTS["min_samples"]))
    out["z_stretch"] = round(_clamp(patch.get("z_stretch"), *_STRETCH_BOUNDS, DEFAULTS["z_stretch"]), 2)
    out["max_points"] = int(_clamp(patch.get("max_points"), *_POINTS_BOUNDS, DEFAULTS["max_points"]))
    out["refresh_ms"] = int(_clamp(patch.get("refresh_ms"), *_REFRESH_BOUNDS, DEFAULTS["refresh_ms"]))
    raw_defs = patch.get("definitions")
    definitions: list[dict[str, Any]] = []
    if isinstance(raw_defs, (list, tuple)):
        for item in raw_defs:
            made = clean_definition(item)
            if made is not None and not any(existing["id"] == made["id"] for existing in definitions):
                definitions.append(made)
    out["definitions"] = definitions or out["definitions"]
    return out


def definition_by_id(settings: Any, ident: Any) -> Optional[dict[str, Any]]:
    """The stored definition with this id (or name), or None."""
    want = slug(ident, fallback="")
    if not want:
        return None
    definitions = clean(settings)["definitions"]
    for definition in definitions:
        if definition.get("id") == want:
            return definition
    for definition in definitions:
        if slug(definition.get("name")) == want:
            return definition
    return None


# ── series in, one timeline out ─────────────────────────────────────────────

def parse_series(rows: Any) -> list[tuple[int, float]]:
    """Leg rows from {ts_ms|t|timestamp_ms, price|close} dicts or (ts, price) pairs, oldest first.

    Rows that carry no usable price are dropped, never zero-filled: a 0 price is a missing print,
    and it would divide a ratio by itself.
    """
    out: list[tuple[int, float]] = []
    if not isinstance(rows, (list, tuple)):
        return out
    for row in rows:
        ts = price = None
        if isinstance(row, dict):
            ts = _num(row.get("ts_ms", row.get("t", row.get("timestamp_ms"))))
            price = _num(row.get("price", row.get("close")))
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            ts, price = _num(row[0]), _num(row[1])
        if ts is None or price is None or price <= 0:
            continue
        out.append((int(ts), float(price)))
    out.sort(key=lambda pair: pair[0])
    return out


def align(series: Any, *, align_ms: int = 60_000, max_gap_ms: int = 0) -> dict[str, Any]:
    """Union of the legs' timestamps, each leg carried forward onto it.

    Each leg is bucketed to `align_ms` first (the last print in a bucket is that bucket's price).
    The composite's timeline is the union of those buckets. A leg with no print in a bucket is
    carried at its last price while the gap is within `max_gap_ms` (0 = carry anything), and it is
    never carried backwards past its first print. A bucket where any leg has nothing to carry is
    dropped, and how often each leg was carried is counted, so the caller can say how much of the
    composite is carried prices.
    """
    grid = max(1_000, int(align_ms or 60_000))
    gap_limit = max(0, int(max_gap_ms or 0))
    per_leg: dict[str, dict[int, float]] = {}
    for symbol, rows in (series if isinstance(series, dict) else {}).items():
        buckets: dict[int, float] = {}
        for ts, price in parse_series(rows):
            buckets[ts - (ts % grid)] = price
        if buckets:
            per_leg[str(symbol)] = buckets
    symbols = sorted(per_leg)
    times = sorted({bucket for buckets in per_leg.values() for bucket in buckets})
    prices: dict[str, list[float]] = {symbol: [] for symbol in symbols}
    carried: dict[str, int] = {symbol: 0 for symbol in symbols}
    last_print: dict[str, Optional[int]] = {symbol: None for symbol in symbols}
    kept: list[int] = []
    for moment in times:
        for symbol in symbols:
            if moment in per_leg[symbol]:
                last_print[symbol] = moment
        column: dict[str, float] = {}
        filled: set[str] = set()
        for symbol in symbols:
            printed = per_leg[symbol].get(moment)
            if printed is not None:
                column[symbol] = printed
                continue
            previous = last_print[symbol]
            if previous is None or (gap_limit and (moment - previous) > gap_limit):
                column = {}
                break
            column[symbol] = per_leg[symbol][previous]
            filled.add(symbol)
        if not column:
            continue
        kept.append(moment)
        for symbol in symbols:
            prices[symbol].append(column[symbol])
            if symbol in filled:
                carried[symbol] += 1
    return {"times": kept, "prices": prices, "carried": carried, "legs": symbols,
            "align_ms": grid, "max_gap_ms": gap_limit}


# ── the arithmetic ──────────────────────────────────────────────────────────

def _mean(values: Sequence[float]) -> Optional[float]:
    return (sum(values) / len(values)) if values else None


def stdev(values: Sequence[float]) -> Optional[float]:
    """Population standard deviation — the window IS the population being described."""
    average = _mean(values)
    if average is None or len(values) < 2:
        return None
    return math.sqrt(sum((value - average) ** 2 for value in values) / len(values))


def median(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """Pearson r, or None when either side has no real dispersion.

    Same rule as the correlation tracker: three samples minimum, and a constant-rate move (every
    step up the same percent) must not read as a perfect correlation — its spread is rounding noise.
    """
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    dy = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if dx <= 0 or dy <= 0:
        return None
    if (dx / math.sqrt(n)) <= 1e-9 * max(abs(mean_x), 1e-9):
        return None
    if (dy / math.sqrt(n)) <= 1e-9 * max(abs(mean_y), 1e-9):
        return None
    return numerator / (dx * dy)


def log_returns(values: Sequence[float]) -> list[float]:
    """Step-to-step log returns of one aligned leg (a non-positive print breaks the chain)."""
    out: list[float] = []
    previous: Optional[float] = None
    for value in values:
        if previous is not None and previous > 0 and value > 0:
            out.append(math.log(value / previous))
        previous = value
    return out


def composite_value(kind: str, legs: Sequence[dict[str, Any]],
                    prices: dict[str, float]) -> Optional[float]:
    """One composite point from the legs' prices at one timestamp, or None when the kind needs a
    leg that has no price (a ratio whose denominator is missing or zero is not a number)."""
    plus = 0.0
    minus = 0.0
    total_weight = 0.0
    seen_plus = seen_minus = False
    for leg in legs:
        price = prices.get(leg["symbol"])
        if price is None:
            return None
        weight = float(leg["weight"])
        total_weight += weight
        if leg["side"] > 0:
            plus += weight * price
            seen_plus = True
        else:
            minus += weight * price
            seen_minus = True
    if kind == "basket":
        return (plus - minus) / total_weight if total_weight > 0 and len(legs) > 0 else None
    if not seen_plus or not seen_minus:
        return None
    if kind == "spread":
        return plus - minus
    if not (minus > 0):
        return None
    if kind == "ratio":
        return plus / minus
    if kind == "basis":
        return (plus - minus) / minus
    return None


def _leg_prices_at(grid: dict[str, Any], index: int) -> dict[str, float]:
    return {symbol: values[index] for symbol, values in grid["prices"].items()}


def premium(kind: str, legs: Sequence[dict[str, Any]], column: dict[str, float],
            values: Sequence[float]) -> tuple[Optional[float], Optional[float], Optional[float], str]:
    """(reference, spread_abs, spread_bps, reference_kind) for one composite series.

    The units are the point of this function. A basis IS a fraction of the leg it is measured
    against, so its bps figure is the value itself (x 10 000) and its absolute figure is the price
    difference at that same level. A spread is a price difference measured against that level. A
    ratio has no quote currency and a one-sided basket has no leg to be measured against, so both
    are measured against their own window median, in bps of that median — a stated rule, printed in
    `reference_kind`, never an implied one.
    """
    short_level: Optional[float] = None
    if kind in BOTH_SIDES:
        level = sum(float(leg["weight"]) * column.get(leg["symbol"], 0.0)
                    for leg in legs if leg["side"] < 0)
        short_level = level if level > 0 else None
    latest = values[-1]
    if kind == "basis" and short_level is not None:
        return short_level, latest * short_level, latest * 10_000.0, "short_leg"
    if kind == "spread" and short_level is not None:
        return short_level, latest, latest / short_level * 10_000.0, "short_leg"
    middle = median(list(values))
    if middle is None or middle <= 0:
        return None, None, None, "window_median"
    return (middle, (latest - middle) if kind == "basket" else None,
            (latest - middle) / middle * 10_000.0, "window_median")


def compose(definition: Any, series: Any, settings: Any = None) -> dict[str, Any]:
    """Compose one synthetic instrument from its legs' series.

    `series` is {symbol: [{ts_ms, price}, ...]} — read the router's own stored candles, or a
    fixture. Returns either a refusal ({"ok": False, "detail": <one plain sentence>}) or the
    composite, its divergence statistics and the plain-English read.
    """
    conf = clean(settings)
    clean_def = clean_definition(definition)
    if clean_def is None:
        return {"ok": False, "detail": "that synthetic instrument has no usable legs — give it a "
                                       "name, a kind and at least one leg"}
    series = series if isinstance(series, dict) else {}
    missing = [leg["symbol"] for leg in clean_def["legs"]
               if not parse_series(series.get(leg["symbol"]))]
    if missing:
        # The refusal names the leg, not the feature: the panel's own instruction is that a symbol
        # only stores history once it has been streamed (its chart opened).
        return {"ok": False, "definition": clean_def, "missing": missing,
                "detail": f"no stored history for {missing[0]} — open its chart first"}

    grid = align({leg["symbol"]: series[leg["symbol"]] for leg in clean_def["legs"]},
                 align_ms=conf["align_ms"], max_gap_ms=conf["max_gap_ms"])
    times = grid["times"]
    if len(times) < 3:
        return {"ok": False, "definition": clean_def, "missing": [],
                "detail": f"the legs line up on only {len(times)} timestamp(s) — at least 3 are "
                          "needed before a composite means anything"}

    values: list[float] = []
    kept_times: list[int] = []
    for index, moment in enumerate(times):
        value = composite_value(clean_def["kind"], clean_def["legs"], _leg_prices_at(grid, index))
        if value is None:
            continue                       # a denominator that is missing or zero is skipped
        values.append(value)
        kept_times.append(moment)
    if len(values) < 3:
        return {"ok": False, "definition": clean_def, "missing": [],
                "detail": "the legs line up but the composite is undefined on almost every "
                          "timestamp — check the legs' sides and weights"}

    reference, spread_abs, spread_bps, reference_kind = premium(
        clean_def["kind"], clean_def["legs"], _leg_prices_at(grid, len(times) - 1), values)
    average = _mean(values)
    dispersion = stdev(values)
    flat = dispersion is None or dispersion <= 0
    covered = len(values) >= conf["min_samples"]
    z_values: list[Optional[float]] = []
    for value in values:
        if flat or average is None or not covered:
            z_values.append(None)
        else:
            z_values.append((value - average) / dispersion)
    z_now = z_values[-1]
    scored = [z for z in z_values if z is not None]
    beyond = (100.0 * sum(1 for z in scored if abs(z) > conf["z_stretch"]) / len(scored)) if scored else None
    # Why a z-score is missing, in the payload's own words: a composite that has not moved at all
    # has no dispersion to score against, and that is a different statement from "too few samples".
    z_reason = "flat" if flat else ("" if covered else "few")

    legs_out: list[dict[str, Any]] = []
    filled_total = 0
    for leg in clean_def["legs"]:
        symbol = leg["symbol"]
        filled = int(grid["carried"].get(symbol, 0))
        filled_total += filled
        legs_out.append({
            "symbol": symbol, "side": leg["side"], "weight": leg["weight"],
            "samples": len(grid["prices"].get(symbol) or []),
            "carried_pct": round(100.0 * filled / len(times), 1) if times else None,
            "first_ms": times[0], "last_ms": times[-1],
        })

    stats: dict[str, Any] = {
        "kind": clean_def["kind"],
        "value_unit": VALUE_UNIT.get(clean_def["kind"], ""),
        "samples": len(values),
        "window_ms": kept_times[-1] - kept_times[0],
        "window_minutes": round((kept_times[-1] - kept_times[0]) / 60_000.0, 1),
        "align_ms": grid["align_ms"],
        "first_ms": kept_times[0],
        "last_ms": kept_times[-1],
        "value": round(values[-1], 8),
        "spread_abs": round(spread_abs, 8) if spread_abs is not None else None,
        "spread_bps": round(spread_bps, 4) if spread_bps is not None else None,
        "reference": round(reference, 8) if reference is not None else None,
        "reference_kind": reference_kind,
        "mean": round(average, 8) if average is not None else None,
        "stdev": round(dispersion, 10) if dispersion is not None else None,
        "z": round(z_now, 4) if z_now is not None else None,
        "z_reason": z_reason,
        "z_stretch": conf["z_stretch"],
        "beyond_stretch_pct": round(beyond, 2) if beyond is not None else None,
        "min": round(min(values), 8),
        "max": round(max(values), 8),
        "carried_pct": round(100.0 * filled_total / (len(times) * max(1, len(clean_def["legs"]))), 1),
        "correlation": None,
        "correlation_pairs": 0,
    }

    returns = {leg["symbol"]: log_returns(grid["prices"].get(leg["symbol"]) or [])
               for leg in clean_def["legs"]}
    pair_values: list[float] = []
    symbols = [leg["symbol"] for leg in clean_def["legs"]]
    for index, first in enumerate(symbols):
        for second in symbols[index + 1:]:
            short = min(len(returns[first]), len(returns[second]))
            if short < 3:
                continue
            r = pearson(returns[first][-short:], returns[second][-short:])
            if r is not None:
                pair_values.append(r)
    if pair_values:
        stats["correlation_pairs"] = len(pair_values)
        stats["correlation"] = round(sum(pair_values) / len(pair_values), 4)

    # The chart gets the tail of the series; the statistics above are always the whole window.
    points = min(conf["max_points"], len(values))
    series_out = [{"t": kept_times[index], "v": round(values[index], 8),
                   "z": round(z_values[index], 4) if z_values[index] is not None else None}
                  for index in range(len(values) - points, len(values))]

    payload = {
        "ok": True,
        "definition": clean_def,
        "stats": stats,
        "legs": legs_out,
        "series": series_out,
        "read": read_sentence(clean_def, stats, window_min=conf["window_min"]),
        "settings": {key: conf[key] for key in ("window_min", "align_ms", "max_gap_ms",
                                               "min_samples", "z_stretch", "max_points",
                                               "refresh_ms")},
        "note": "Composite prices come from the legs' own stored 1-minute closes; nothing here is "
                "interpolated or invented.",
    }
    if stats["samples"] < conf["min_samples"]:
        payload["detail"] = (f"only {stats['samples']} aligned point(s) — the z-score and the "
                             f"divergence read need {conf['min_samples']}")
    return payload


# ── the plain-English read ──────────────────────────────────────────────────

def human_window(minutes: Any, *, hyphen: bool = False) -> str:
    """'4 hours' / '90 minutes' / '2 days' — the window as the sentence says it.

    `hyphen=True` gives the attributive form ('4-hour median'), which is the only place the two
    ever differ.
    """
    value = _num(minutes)
    if value is None or value <= 0:
        return "the window"
    if value < 60:
        count = int(value)
        return f"{count}-minute" if hyphen else f"{count} minute" + ("" if count == 1 else "s")
    if value < 1440:
        hours = value / 60.0
        text = f"{hours:.0f}" if abs(hours - round(hours)) < 0.05 else f"{hours:.1f}"
        if hyphen:
            return f"{text}-hour"
        return text + (" hour" if text == "1" else " hours")
    days = value / 1440.0
    text = f"{days:.0f}" if abs(days - round(days)) < 0.05 else f"{days:.1f}"
    if hyphen:
        return f"{text}-day"
    return text + (" day" if text == "1" else " days")


def _bps_text(bps: Optional[float]) -> str:
    if bps is None:
        return "no spread"
    return f"{abs(bps):.1f} bps"


def _sigma_text(z: Optional[float]) -> str:
    if z is None:
        return "no z-score yet"
    if abs(z) < 0.2:
        return f"flat, {abs(z):.1f} sigma off the window's mean"
    word = "rich" if z > 0 else "cheap"
    return f"{abs(z):.1f} sigma {word}"


def read_sentence(definition: Any, stats: Any, *, window_min: Any = None) -> str:
    """The one line a trader reads: 'BTC perp is trading 14.2 bps over spot — 1.4 sigma rich over
    the last 4 hours'. No z-score yet says so instead of printing a zero sigma."""
    clean_def = clean_definition(definition) or {}
    stats = stats if isinstance(stats, dict) else {}
    name = str(clean_def.get("name") or "synthetic")
    bps = _num(stats.get("spread_bps"))
    z = _num(stats.get("z"))
    reference_kind = str(stats.get("reference_kind") or "window_median")
    # The ACTUAL cover of the series wins over the requested lookback: a 4-hour panel with 40
    # minutes of history says "40 minutes", which is the honest window behind the number.
    cover = _num(stats.get("window_minutes"))
    if cover is None or cover <= 0:
        cover = _num(window_min)
    window = human_window(cover)
    direction = "over" if (bps or 0) >= 0 else "under"
    if reference_kind == "short_leg":
        short_legs = [leg for leg in clean_def.get("legs") or [] if leg.get("side", 1) < 0]
        against = str(short_legs[0]["symbol"]) if short_legs else "the second leg"
        head = f"{name} is trading {_bps_text(bps)} {direction} {against}"
    else:
        adjective = "above" if (bps or 0) >= 0 else "below"
        head = (f"{name} is trading {_bps_text(bps)} {adjective} its "
                f"{human_window(cover, hyphen=True)} median")
    if z is None:
        if str(stats.get("z_reason") or "") == "flat":
            return (f"{head} — the composite has not moved across the window, so there is no "
                    "z-score to report")
        return f"{head} — no z-score yet: {stats.get('samples') or 0} aligned point(s)"
    tail = _sigma_text(z)
    return f"{head} — {tail} over the last {window}"


# ── the route: stored history in, a composite out ───────────────────────────
# The handlers below are the only part that touches the engine, and they never raise: a missing
# engine, a missing symbol or a missing key comes back as one plain sentence.

def _settings() -> dict[str, Any]:
    """This feature's own config block, cleaned. A config that has never seen the block gets the
    defaults, so the panel works on a first run (and the parent's registration is additive)."""
    try:
        from orderflow_system.desktop import config_store
        atlas = (config_store.load_config() or {}).get("atlas") or {}
        return clean(atlas.get("synthetic"))
    except Exception:                                  # noqa: BLE001 — defaults are always valid
        return clean(None)


async def _stored_rows(symbol: str, start_ms: int, end_ms: int) -> list[tuple[int, float]]:
    """Stored 1-minute closes for one leg, from the engine's database.

    The database is the source (it survives a restart and a download); the live pipeline's own
    recent candles are the fallback for a symbol the engine has streamed but not yet flushed.
    Empty means "this build has no history for that symbol", which is what the panel refuses on.
    """
    system = _engine_system()
    if system is None:
        return []
    rows: list[tuple[int, float]] = []
    db = getattr(system, "db", None)
    if db is not None:
        try:
            candles = await db.get_candles(symbol, "1m", int(start_ms), int(end_ms))
            rows = [(int(c.timestamp_ms), float(c.close)) for c in candles
                    if c is not None and getattr(c, "close", None)]
        except Exception:                              # noqa: BLE001 — history is optional
            rows = []
    if len(rows) < 3:
        pipeline = (getattr(system, "pipelines", {}) or {}).get(symbol)
        builder = getattr(pipeline, "candle_builder", None)
        if builder is not None:
            try:
                held = [(int(c.timestamp_ms), float(c.close))
                        for c in builder.get_recent_candles(5_000)
                        if c is not None and getattr(c, "close", None)
                        and int(start_ms) <= int(c.timestamp_ms) <= int(end_ms)]
                if len(held) > len(rows):
                    rows = held
            except Exception:                          # noqa: BLE001
                pass
    rows.sort(key=lambda pair: pair[0])
    return rows


def _engine_system() -> Any:
    """The running engine's system object, or None (the app can be open with the engine stopped)."""
    try:
        from orderflow_system.desktop import engine as engine_mod
        return getattr(engine_mod.engine, "system", None)
    except Exception:                                  # noqa: BLE001
        return None


async def _known_symbols() -> list[dict[str, Any]]:
    """Every instrument this build could compose with: the engine's live ones, the stored ones, and
    the enabled ones. `live` and `history` say which is which — the builder marks each leg, so a
    leg that cannot answer is visible before the compose is asked for."""
    system = _engine_system()
    live = set((getattr(system, "pipelines", {}) or {}).keys()) if system is not None else set()
    stored: set[str] = set()
    db = getattr(system, "db", None) if system is not None else None
    if db is not None:
        try:
            stored = {str(name) for name in (await db.tick_instruments() or []) if name}
        except Exception:                              # noqa: BLE001
            stored = set()
    enabled: list[str] = []
    try:
        from orderflow_system.desktop import config_store
        cfg = config_store.load_config() or {}
        enabled = [str(item.get("symbol") or "") for item in (cfg.get("instruments") or [])
                   if isinstance(item, dict) and item.get("symbol")]
    except Exception:                                  # noqa: BLE001
        enabled = []
    names = sorted({name.upper() for name in (list(live) + list(stored) + enabled) if name})
    return [{"symbol": name, "live": name in live, "history": name in stored} for name in names]


def _persist(definition: dict[str, Any]) -> tuple[bool, str]:
    """Store one accepted definition in this feature's config block, replacing the same id.

    Returns (saved, sentence). A store that refuses keeps the definition in the answer — the panel
    can compose it for this session either way, and says so rather than claiming a save.
    """
    try:
        from orderflow_system.desktop import config_store
        cfg = config_store.load_config() or {}
        atlas = cfg.get("atlas")
        if not isinstance(atlas, dict):
            atlas = {}
            cfg["atlas"] = atlas
        block = clean(atlas.get("synthetic"))
        definitions = [item for item in block["definitions"] if item.get("id") != definition["id"]]
        if len(definitions) >= MAX_DEFINITIONS:
            # The store is full: refuse, and keep the definition in the answer, rather than evicting
            # the oldest behind the writer's back (§148 T4-F8).
            return False, (f"the store holds {MAX_DEFINITIONS} definitions; "
                           "delete one before saving another")
        definitions.append(definition)
        block["definitions"] = definitions
        atlas["synthetic"] = block
        config_store.save_config(cfg)
        return True, ""
    except Exception as exc:                           # noqa: BLE001 — a read-only store is not fatal
        return False, f"the definition could not be stored ({type(exc).__name__})"


@router.get("/synthetic")
async def synthetic_list() -> dict[str, Any]:
    """Every definition this build carries, the symbols it can read, and the settings it applies."""
    conf = _settings()
    symbols = await _known_symbols()
    return {
        "ok": True,
        "definitions": conf["definitions"],
        "symbols": symbols,
        "settings": {key: conf[key] for key in ("window_min", "align_ms", "max_gap_ms",
                                               "min_samples", "z_stretch", "max_points",
                                               "refresh_ms")},
        "kinds": list(KINDS),
        "note": "A synthetic instrument is arithmetic over the legs' own stored 1-minute candles — "
                "a leg with no stored history is refused by name.",
    }


@router.get("/synthetic/compose")
async def synthetic_compose(definition: str = Query(default=""),
                            window_min: int = Query(default=0, ge=0, le=10_080),
                            points: int = Query(default=0, ge=0, le=2_000)) -> dict[str, Any]:
    """Compose one definition from its legs' stored candles.

    A missing definition, a stopped engine or a leg with no history all come back as
    {"ok": False, "detail": "<one plain sentence>"} — never a 500 and never a fabricated series.
    """
    conf = _settings()
    found = definition_by_id(conf, definition)
    if found is None:
        asked = str(definition or "").strip()
        return {"ok": False,
                "detail": (f"no synthetic instrument called {asked!r} — pick one from the list or "
                           "build it first") if asked
                          else "name a synthetic instrument to compose"}
    if window_min:
        conf["window_min"] = int(_clamp(window_min, *_WINDOW_BOUNDS, conf["window_min"]))
    if points:
        conf["max_points"] = int(_clamp(points, *_POINTS_BOUNDS, conf["max_points"]))
    if _engine_system() is None:
        return {"ok": False, "definition": found, "missing": [],
                "detail": "the engine is not running — start it so the legs store some candles, "
                          "then compose again"}
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - int(conf["window_min"] * 60_000)
    series: dict[str, list[tuple[int, float]]] = {}
    for leg in found["legs"]:
        series[leg["symbol"]] = await _stored_rows(leg["symbol"], start_ms, now_ms)
    payload = compose(found, series, conf)
    payload["window_min"] = conf["window_min"]
    payload["at_ms"] = now_ms
    if payload.get("ok"):
        payload["read"] = read_sentence(found, payload["stats"], window_min=conf["window_min"])
    return payload


@router.post("/synthetic")
async def synthetic_accept(payload: dict = Body(default={})) -> dict[str, Any]:
    """Validate one definition and store it in this feature's config block.

    The body is the definition itself or {"definition": {...}}. A definition that cannot be read
    comes back with the problems by name; an accepted one comes back canonicalised, with `saved`
    telling the truth about whether it reached the config file.
    """
    payload = payload if isinstance(payload, dict) else {}
    raw = payload.get("definition") if isinstance(payload.get("definition"), dict) else payload
    definition, problems = check_definition(raw)
    if definition is None:
        return {"ok": False, "problems": problems,
                "detail": problems[0] if problems else "that synthetic instrument could not be read"}
    saved, failure = _persist(definition)
    conf = _settings()
    return {
        "ok": True,
        "definition": definition,
        "definitions": conf["definitions"],
        "saved": saved,
        "detail": "" if saved else failure,
        "note": "stored definitions are composed on demand; each leg still needs its own stored "
                "history.",
    }
