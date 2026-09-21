"""Per-instrument data quality — the cockpit that says how good the stored history is.

ATAS markets "reload back-adjusted data / self-repair" as a differentiator, and there is a reason: a
footprint, a volume profile or a CVD line is only as trustworthy as the history under it, and when a
user suspects a hole the honest move is to SHOW the hole instead of letting a study quietly read
around it. ModFlow already stores its own history (`data/database.py` — ticks and candles) and
already has a live age surface (`atlas/freshness.py` + `desktop/ui/freshness.js`, P1-10). What was
missing is the per-instrument scorecard: coverage, gaps longer than a few cadence steps, duplicates,
out-of-order stamps, the age of the newest sample, one letter verdict, one plain sentence, and the
repairs the app can actually run.

The computation is pure — `scorecard()` takes plain timestamps in and returns a plain dict — so every
number here is pinned offline by `orderflow_system/test_dataquality.py`. The route at the bottom is
the only part that touches SQLite, and it reads through the app's own stored-history accessors
(`Database.get_recent_ticks` for ticks, `Database.get_candles` for candle series — the accessors
`GET /api/control/trades` reads too; `Database.count_ticks` belongs to that route, not to this
read) with the same bound: the read walks backwards from the newest row and
stops at the cap, because a day of a liquid instrument is millions of prints and a panel is not
allowed to read them all into memory.

Honesty rules this module keeps:

* **The refusal is a sentence, never zeros.** A symbol with no stored rows answers
  ``no stored history for <symbol> yet — open a chart and let it load`` and the panel prints it.
* **The expectation is scaled to the venue's own hours.** A stock does not print at 03:00 UTC, so a
  stock's coverage is measured against its ~6.5 open hours a weekday (``DEFAULTS["sessions"]``), not
  against a 24 h clock that would always read ~27% and teach the user to ignore the number.
* **What the read covered is what is judged.** The read is capped at ``max_samples`` per instrument;
  the scorecard then judges the window it actually saw, sets ``capped: True`` and names the shorter
  window in its sentence instead of pretending to have looked at the whole one.
* **Nothing is invented.** Timestamps in, timestamps counted; no spacing is guessed and no missing
  sample is filled in with an estimate. A gap is a real wall-clock hole between two stored stamps.

The hints name six repair actions (`refetch`, `backfill`, `dedupe`, `order`, `clock`, `trim`) and one
of them has a real path: `POST /api/control/backfill` (re-fetch a day window from the venue's public
archive) answers both `refetch` and `backfill`. The other four say plainly that this build has no
route for them — a named action with `available: false` and no button — rather than offering a
control that cannot do what it says.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Iterable, Optional

from fastapi import APIRouter, Query

from orderflow_system.atlas.freshness import window_ms as fresh_window_ms

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/atlas", tags=["atlas"])

#: The asset classes the cadence/session tables know. Anything else is "other".
CLASSES: tuple[str, ...] = ("crypto", "forex", "indices", "metals", "energy", "stocks", "other")
DEFAULT_CLASS = "other"

#: What each letter means, in plain words. Printed beside the letter, never instead of it.
VERDICT_NOTES: dict[str, str] = {
    "A": "clean — nothing to repair",
    "B": "usable — the holes below are worth a look before a long study",
    "C": "partly usable — refetch the holes before trusting a study over this window",
    "D": "sparse — read studies over this window as indicative only",
    "F": "effectively missing — do not read studies over this window",
}

#: The one route a repair hint may point at. It exists (desktop/api.py) and is a POST; the hint
#: carries the path so the panel can print where the repair lives, never a button that 404s.
#: (§148 T5-F-12: the trim hint used to point at `storage/prune` too — retention trims the old
#: end, which cannot uncap a read that counts from the newest one, so that hint now names the
#: window setting instead and offers no route.)
ROUTE_BACKFILL = "/api/control/backfill"

DEFAULTS: dict[str, Any] = {
    "enabled": True,
    #: ticks | candles — which stored series the cockpit reads. Ticks are what the store always has;
    #: a candle series is one row a minute, which makes it the cheap series for a wide cockpit.
    "kind": "ticks",
    "timeframe": "1m",             # the candle series, when kind is candles
    "window_h": 24.0,              # how much history the per-instrument scorecard judges
    "rows_window_h": 6.0,          # the shorter window the cockpit's own row list asks for
    "gap_mult": 3,                 # cadence steps with no sample that make a hole a gap
    "merge_present": 2,            # samples needed to end a gap — fewer are islands inside it
    "keep_gaps": 20,               # gap rows kept per instrument (biggest first)
    "max_samples": 60_000,         # samples read per instrument — the read is capped, and says so
    "max_symbols": 24,             # instruments the cockpit lists in one pass
    "cadence_s": {                 # expected seconds between samples, per asset class
        "crypto": 1, "forex": 1, "indices": 1, "metals": 1, "energy": 1,
        "stocks": 5, "other": 5,
    },
    "candle_cadence_s": 60,        # a candle series is judged one closed bar at a time
    "sessions": {                  # the venue's own hours — the expectation scales to these
        "crypto": {"open_utc_h": 0.0, "open_h_per_day": 24.0, "weekend_open": True},
        "forex": {"open_utc_h": 22.0, "open_h_per_day": 23.5, "weekend_open": False},
        "indices": {"open_utc_h": 13.5, "open_h_per_day": 23.0, "weekend_open": False},
        "metals": {"open_utc_h": 22.0, "open_h_per_day": 23.0, "weekend_open": False},
        "energy": {"open_utc_h": 22.0, "open_h_per_day": 23.0, "weekend_open": False},
        "stocks": {"open_utc_h": 13.5, "open_h_per_day": 6.5, "weekend_open": False},
        "other": {"open_utc_h": 0.0, "open_h_per_day": 24.0, "weekend_open": True},
    },
    #: The verdict ladder. A is the pass; each letter below it is a wider net of problems.
    "min_coverage_pct": 99.0,      # A needs this much coverage
    "warn_coverage_pct": 95.0,     # B needs this much
    "low_coverage_pct": 80.0,      # C needs this much
    "floor_coverage_pct": 50.0,    # D needs this much; below it the verdict is F
    "gap_a_s": 60.0,               # an A tolerates no hole longer than this
    "gap_b_s": 300.0,              # a B tolerates no hole longer than this
    "stale_a_s": 300.0,            # an A's newest sample is no older than this
    "stale_b_s": 1800.0,           # a B's is no older than this
    "dup_b": 50,                   # extra duplicate rows a B tolerates
    "order_b": 50,                 # out-of-order stamps a B tolerates
    #: Empty = the config's own enabled instruments, which is what the cockpit should list.
    "symbols": [],
}


# ══════════════════════════════════════════════════════════════
# Settings
# ══════════════════════════════════════════════════════════════

def _int_in(value: Any, lo: int, hi: int, default: Any) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        try:
            return max(lo, min(hi, int(default)))
        except (TypeError, ValueError):                    # pragma: no cover - DEFAULTS are sane
            return lo


def _float_in(value: Any, lo: float, hi: float, default: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    if number != number:                                   # NaN is not a threshold
        number = float(default)
    return max(lo, min(hi, number))


def clean(patch: Any) -> dict[str, Any]:
    """The ``data_quality`` block, coerced and clamped — junk falls back to the documented defaults.

    Same contract as ``storage.clamp_storage_settings``: a hand-edited config.json can tune every
    number here and can never break the panel. Three things beyond clamping:

    * the coverage ladder is re-ordered (`min >= warn >= low >= floor`), so a config that inverts the
      bars cannot make "A" reachable below "C";
    * the cadence and session tables are rebuilt class by class, so a missing or half-written table
      is repaired to the defaults instead of silently losing a whole asset class;
    * ``symbols`` is trimmed, upper-cased and de-duplicated — an empty list means "the config's own
      enabled instruments", which is what the route then reads.
    """
    raw = patch if isinstance(patch, dict) else {}

    out: dict[str, Any] = {}
    out["enabled"] = bool(raw.get("enabled", DEFAULTS["enabled"]))
    kind = str(raw.get("kind") or DEFAULTS["kind"]).strip().lower()
    out["kind"] = kind if kind in ("ticks", "candles") else str(DEFAULTS["kind"])
    frame = str(raw.get("timeframe") or DEFAULTS["timeframe"]).strip().lower()
    out["timeframe"] = "".join(ch for ch in frame if ch.isalnum())[:8] or str(DEFAULTS["timeframe"])

    out["window_h"] = _float_in(raw.get("window_h"), 0.05, 720.0, DEFAULTS["window_h"])
    out["rows_window_h"] = _float_in(raw.get("rows_window_h"), 0.05, 720.0, DEFAULTS["rows_window_h"])
    out["gap_mult"] = _int_in(raw.get("gap_mult"), 1, 10_000, DEFAULTS["gap_mult"])
    out["merge_present"] = _int_in(raw.get("merge_present"), 1, 1_000, DEFAULTS["merge_present"])
    out["keep_gaps"] = _int_in(raw.get("keep_gaps"), 0, 500, DEFAULTS["keep_gaps"])
    out["max_samples"] = _int_in(raw.get("max_samples"), 100, 2_000_000, DEFAULTS["max_samples"])
    out["max_symbols"] = _int_in(raw.get("max_symbols"), 1, 200, DEFAULTS["max_symbols"])
    out["candle_cadence_s"] = _int_in(raw.get("candle_cadence_s"), 1, 86_400,
                                      DEFAULTS["candle_cadence_s"])

    cadence_raw = raw.get("cadence_s") if isinstance(raw.get("cadence_s"), dict) else {}
    out["cadence_s"] = {
        klass: _int_in(cadence_raw.get(klass), 1, 3_600, DEFAULTS["cadence_s"][klass])
        for klass in CLASSES
    }

    sessions_raw = raw.get("sessions") if isinstance(raw.get("sessions"), dict) else {}
    sessions: dict[str, dict[str, Any]] = {}
    for klass in CLASSES:
        base = DEFAULTS["sessions"][klass]
        given = sessions_raw.get(klass) if isinstance(sessions_raw.get(klass), dict) else {}
        sessions[klass] = {
            "open_utc_h": _float_in(given.get("open_utc_h"), 0.0, 24.0, base["open_utc_h"]),
            "open_h_per_day": _float_in(given.get("open_h_per_day"), 0.25, 24.0,
                                        base["open_h_per_day"]),
            "weekend_open": bool(given.get("weekend_open", base["weekend_open"])),
        }
    out["sessions"] = sessions

    ladder = {
        "min_coverage_pct": _float_in(raw.get("min_coverage_pct"), 0.0, 100.0,
                                      DEFAULTS["min_coverage_pct"]),
        "warn_coverage_pct": _float_in(raw.get("warn_coverage_pct"), 0.0, 100.0,
                                       DEFAULTS["warn_coverage_pct"]),
        "low_coverage_pct": _float_in(raw.get("low_coverage_pct"), 0.0, 100.0,
                                      DEFAULTS["low_coverage_pct"]),
        "floor_coverage_pct": _float_in(raw.get("floor_coverage_pct"), 0.0, 100.0,
                                        DEFAULTS["floor_coverage_pct"]),
    }
    ladder["warn_coverage_pct"] = min(ladder["warn_coverage_pct"], ladder["min_coverage_pct"])
    ladder["low_coverage_pct"] = min(ladder["low_coverage_pct"], ladder["warn_coverage_pct"])
    ladder["floor_coverage_pct"] = min(ladder["floor_coverage_pct"], ladder["low_coverage_pct"])
    out.update(ladder)

    out["gap_a_s"] = _float_in(raw.get("gap_a_s"), 0.0, 86_400.0, DEFAULTS["gap_a_s"])
    out["gap_b_s"] = max(out["gap_a_s"], _float_in(raw.get("gap_b_s"), 0.0, 86_400.0,
                                                   DEFAULTS["gap_b_s"]))
    out["stale_a_s"] = _float_in(raw.get("stale_a_s"), 0.0, 86_400.0, DEFAULTS["stale_a_s"])
    out["stale_b_s"] = max(out["stale_a_s"], _float_in(raw.get("stale_b_s"), 0.0, 86_400.0,
                                                       DEFAULTS["stale_b_s"]))
    out["dup_b"] = _int_in(raw.get("dup_b"), 0, 1_000_000, DEFAULTS["dup_b"])
    out["order_b"] = _int_in(raw.get("order_b"), 0, 1_000_000, DEFAULTS["order_b"])

    wanted = raw.get("symbols") if isinstance(raw.get("symbols"), list) else []
    seen: list[str] = []
    for item in wanted:
        if not isinstance(item, str):                      # a number is not a symbol
            continue
        sym = item.strip().upper()
        if sym and sym not in seen:
            seen.append(sym)
    out["symbols"] = seen[:out["max_symbols"]]
    return out


# ══════════════════════════════════════════════════════════════
# Small, plain formatters (shared with the panel's wording)
# ══════════════════════════════════════════════════════════════

def fmt_duration(ms: Any) -> str:
    """A span in the words a person reads: "42 s", "4 m 12 s", "3 h 07 m", "2 d 4 h".

    Half-up, not Python's banker's rounding: the panel repeats these words with ``Math.round``
    and the two must not disagree at half-seconds (§148 T5-F-10 — 2500 ms read "2 s" beside
    the panel's "3 s").
    """
    total = max(0, int(float(ms or 0) / 1000.0 + 0.5))
    if total < 60:
        return f"{total} s"
    minutes, seconds = divmod(total, 60)
    if minutes < 60:
        return f"{minutes} m {seconds:02d} s"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} h {minutes:02d} m"
    days, hours = divmod(hours, 24)
    return f"{days} d {hours} h"


def fmt_clock(ms: Any) -> str:
    """The UTC clock of an instant, minute resolution ("03:12") — the zone is named by the caller."""
    try:
        stamp = float(ms or 0) / 1000.0
    except (TypeError, ValueError):                        # pragma: no cover - defensive
        return "—"
    return time.strftime("%H:%M", time.gmtime(stamp))


def fmt_pct(value: Any) -> str:
    """A percentage without a trailing ".0": 96.5 -> "96.5", 96.0 -> "96"."""
    try:
        number = round(float(value), 1)
    except (TypeError, ValueError):                        # pragma: no cover - defensive
        return "0"
    if abs(number - round(number)) < 0.05:
        return str(int(round(number)))
    return f"{number:.1f}"


def fmt_window(seconds: Any) -> str:
    """A window as it is spoken: "24 h", "90 m", "1 h 12 m"."""
    total = max(1, int(round(float(seconds or 0))))
    if total < 3600:
        return f"{max(1, total // 60)} m" if total >= 60 else f"{total} s"
    hours, rest = divmod(total, 3600)
    if rest < 60:
        return f"{hours} h"
    return f"{hours} h {rest // 60:02d} m"


# ══════════════════════════════════════════════════════════════
# The expectation: cadence, the venue's hours, and the slots they imply
# ══════════════════════════════════════════════════════════════

def cadence_ms_for(asset_class: str, kind: str = "ticks", settings: Optional[dict[str, Any]] = None) -> int:
    """Expected milliseconds between two samples of this series.

    A candle series is judged one closed bar at a time (``candle_cadence_s``, 60 by default); a tick
    series is judged against its asset class (``cadence_s``: 1 s for the 24-hour venues, 5 s for
    stocks, whose prints come in bursts anyway).
    """
    cfg = settings if isinstance(settings, dict) and settings else DEFAULTS
    klass = str(asset_class or "").strip().lower()
    if klass not in CLASSES:
        klass = DEFAULT_CLASS
    if str(kind or "").strip().lower() == "candles":
        return int(cfg.get("candle_cadence_s") or DEFAULTS["candle_cadence_s"]) * 1000
    table = cfg.get("cadence_s") if isinstance(cfg.get("cadence_s"), dict) else {}
    seconds = table.get(klass, DEFAULTS["cadence_s"][klass])
    return int(seconds) * 1000


def session_open_ms(from_ms: int, to_ms: int, asset_class: str,
                    settings: Optional[dict[str, Any]] = None) -> int:
    """Milliseconds of ``[from_ms, to_ms]`` that fall inside the venue's own trading hours.

    The session is placed by ``open_utc_h`` each UTC day and lasts ``open_h_per_day``; one that runs
    past midnight is counted on both days it touches. Weekends contribute nothing unless the venue
    trades then, so a Saturday on a stock says "nothing was expected" instead of "everything is
    missing" — the difference between a data fault and a closed market.
    """
    cfg = settings if isinstance(settings, dict) and settings else DEFAULTS
    klass = str(asset_class or "").strip().lower()
    if klass not in CLASSES:
        klass = DEFAULT_CLASS
    table = cfg.get("sessions") if isinstance(cfg.get("sessions"), dict) else {}
    base = DEFAULTS["sessions"][klass]
    entry = table.get(klass) if isinstance(table.get(klass), dict) else base
    hours = _float_in(entry.get("open_h_per_day"), 0.25, 24.0, base["open_h_per_day"])
    start_h = _float_in(entry.get("open_utc_h"), 0.0, 24.0, base["open_utc_h"])
    weekend_open = bool(entry.get("weekend_open", base["weekend_open"]))
    if to_ms <= from_ms:
        return 0
    if hours >= 24.0 and weekend_open:
        return int(to_ms - from_ms)                          # a 24/7 venue: always open
    opened = 0
    first_day, last_day = int(from_ms // 86_400_000) - 1, int(to_ms // 86_400_000) + 1
    for day in range(max(0, first_day), min(last_day, first_day + 4_002) + 1):
        # Epoch day 0 (1970-01-01) was a Thursday, so `(day + 3) % 7` numbers weekdays from
        # Monday: 5 is Saturday, 6 is Sunday. (§148 T5-F-15: the old `weekend_days` counter was
        # dead in production — nothing called it — so the rule lives here, at its only reader.)
        if not weekend_open and (day + 3) % 7 in (5, 6):      # Saturday, Sunday
            continue
        begin = day * 86_400_000 + int(start_h * 3_600_000)
        end = begin + int(hours * 3_600_000)
        opened += max(0, min(int(to_ms), end) - max(int(from_ms), begin))
    return int(opened)


def session_factor(from_ms: int, to_ms: int, asset_class: str,
                   settings: Optional[dict[str, Any]] = None) -> float:
    """The share of the window the venue is actually open — 1.0 for a 24/7 crypto pair, 0.5 for a
    one-hour stock window that straddles the open. Never zero: a factor of 0 would make every
    coverage percentage infinite."""
    window = int(to_ms) - int(from_ms)
    if window <= 0:
        return 1.0
    return max(0.02, min(1.0, session_open_ms(from_ms, to_ms, asset_class, settings) / window))


def session_note(asset_class: str, settings: Optional[dict[str, Any]] = None) -> str:
    """One plain line when the expectation was scaled, empty when the venue is 24/7."""
    factor = session_factor(0, 86_400_000, asset_class, settings)
    if factor >= 0.95:
        return ""
    cfg = settings if isinstance(settings, dict) and settings else DEFAULTS
    klass = asset_class if asset_class in CLASSES else DEFAULT_CLASS
    entry = cfg["sessions"][klass]
    hours = float(entry.get("open_h_per_day") or 0.0)
    words = f"{klass} trades about {hours:g} h a day — the expectation is scaled to that"
    if not entry.get("weekend_open"):
        words += ", and weekends are closed"
    return words


def infer_asset_class(symbol: str, table: Optional[dict[str, Any]] = None) -> str:
    """The asset class of a symbol: the config's own table first, then a shape we can name.

    Never a guess about an unknown name: a slash or a ``USDT``/``USDC`` suffix is a crypto pair, six
    letters of FX is forex, and anything else is "other" (which uses the default cadence and a 24/7
    session). The route prefers the config's ``ASSET_CLASS`` map, so a symbol the app knows is never
    classified by name.
    """
    sym = str(symbol or "").strip().upper()
    given = table if isinstance(table, dict) else {}
    hit = str(given.get(sym) or "").strip().lower()
    if hit in CLASSES:
        return hit
    if "/" in sym or sym.endswith("USDT") or sym.endswith("USDC") or sym.endswith("-USD"):
        return "crypto"
    if len(sym) == 6 and sym.isalpha():
        return "forex"
    return DEFAULT_CLASS


# ══════════════════════════════════════════════════════════════
# The pure computation
# ══════════════════════════════════════════════════════════════

def to_timestamp(sample: Any) -> int:
    """One epoch-millisecond stamp out of whatever the caller has: an int, a dict, a Tick/Candle.

    0 means "not a usable stamp" — it is dropped rather than counted as 1970.
    """
    if isinstance(sample, bool):
        return 0
    if isinstance(sample, (int, float)):
        try:
            return max(0, int(sample))
        except (TypeError, ValueError, OverflowError):     # pragma: no cover - defensive
            return 0
    if isinstance(sample, dict):
        for key in ("ts_ms", "ts", "timestamp_ms", "time_ms"):
            if sample.get(key) is not None:
                return to_timestamp(sample.get(key))
        return 0
    for key in ("timestamp_ms", "ts_ms", "ts"):
        value = getattr(sample, key, None)
        if value is not None:
            return to_timestamp(value)
    return 0


def _as_list(items: Any) -> list[Any]:
    """Whatever a caller passed where a list of samples was expected, as a list.

    A number, a string or anything else that cannot be iterated is "no samples" rather than a
    TypeError: a cockpit that raises on a malformed input is worse than one that says nothing is
    stored.
    """
    if items is None or isinstance(items, (int, float, bool, str, bytes)):
        return []
    try:
        return list(items)
    except TypeError:                                          # pragma: no cover - defensive
        return []


def _epoch_ms(value: Any, fallback: int) -> int:
    """A usable epoch-millisecond integer, or the fallback: junk in, fallback out, never a raise."""
    if value is None:
        return fallback
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    return number if number > 0 else fallback


def detect_gaps(stamps: Iterable[int], cadence_ms: int, *, min_slots: int = 3,
                merge_present: int = 2, keep: int = 20) -> tuple[list[dict[str, Any]], int, int]:
    """Holes between stored samples — biggest first, with the wall-clock range of each.

    The timeline is walked in cadence slots. A hole is a run of empty slots, reported when it is at
    least ``min_slots`` slots wide (a narrower one is a "hole": counted, not listed). ``merge_present``
    is the merging rule — a hole is only closed once that many samples in a row sit inside it, so one
    stray print in the middle of a ten-minute hole is a ten-minute hole, not two five-minute ones.

    ``from_ms``/``to_ms`` are the two stored stamps that bracket the hole and ``gap_ms`` is the real
    elapsed time between them; ``missing_slots``/``samples_inside`` split that time into the slots
    with nothing in them and the samples that were stored inside it. Returns (the biggest ``keep``
    gaps, holes below the threshold, the total number of gaps before that cut).
    """
    cadence = max(1, int(cadence_ms or 1000))
    ordered = sorted({stamp for stamp in (to_timestamp(s) for s in _as_list(stamps)) if stamp > 0})
    if len(ordered) < 2:
        return [], 0, 0
    anchor = ordered[0]
    slots = [(stamp - anchor) // cadence for stamp in ordered]
    spans = max(1, int(merge_present))

    # The walk: a hole opens at a step wider than one slot and closes when `spans` samples arrive
    # back to back (or at the end of the history). One stray print inside a ten-minute hole is a
    # ten-minute hole, not two five-minute ones; `merge_present = 1` means "every hole on its own",
    # which is the setting that keeps a sparse store's holes from folding into one giant hole.
    hole_steps = [index for index in range(len(ordered) - 1)
                  if slots[index + 1] - slots[index] > 1]
    groups: list[tuple[int, int]] = []
    if spans == 1:
        groups = [(step, step) for step in hole_steps]
    else:
        index = 0
        while index < len(ordered) - 1:
            if slots[index + 1] - slots[index] <= 1:
                index += 1
                continue
            first_pair, last_pair, streak = index, index, 0
            index += 1
            while index < len(ordered) - 1:
                if slots[index + 1] - slots[index] <= 1:
                    streak += 1
                    if streak >= spans:
                        break
                else:
                    streak, last_pair = 0, index
                index += 1
            groups.append((first_pair, last_pair))
            index = last_pair + 1

    gaps: list[dict[str, Any]] = []
    holes = 0
    for first_pair, last_pair in groups:
        from_ms, to_ms = ordered[first_pair], ordered[last_pair + 1]
        span = to_ms - from_ms
        if span < max(1, int(min_slots)) * cadence:
            holes += 1
            continue
        islands = last_pair - first_pair
        missing = (slots[last_pair + 1] - slots[first_pair]) - 1 - islands
        gaps.append({
            "from_ms": from_ms, "to_ms": to_ms, "gap_ms": span,
            "missing_slots": max(0, missing), "missing_ms": max(0, missing) * cadence,
            "samples_inside": islands,
            "from_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime(from_ms / 1000.0)),
        })
    gaps.sort(key=lambda row: row["gap_ms"], reverse=True)
    total = len(gaps)
    return gaps[:max(0, int(keep))], holes, total


def count_duplicates(stamps: Iterable[int]) -> dict[str, Any]:
    """Duplicate stamps: how many timestamps repeat, and how many extra rows they are."""
    seen: dict[int, int] = {}
    for stamp in stamps or []:
        seen[stamp] = seen.get(stamp, 0) + 1
    repeated = sorted(s for s, n in seen.items() if n > 1)
    extra = sum(n - 1 for n in seen.values() if n > 1)
    return {"n": len(repeated), "extra": extra, "first_ms": repeated[0] if repeated else 0}


def count_disorder(stamps: Iterable[int]) -> dict[str, Any]:
    """Out-of-order stamps: how many steps went backwards, and where the first one is."""
    previous: Optional[int] = None
    backwards = 0
    first = 0
    for stamp in stamps or []:
        if previous is not None and stamp < previous:
            backwards += 1
            if not first:
                first = stamp
        previous = stamp
    return {"n": backwards, "first_ms": first}


def verdict_for(*, coverage_pct: float, biggest_gap_ms: int, stale_ms: int,
                duplicates_extra: int, out_of_order: int,
                settings: Optional[dict[str, Any]] = None) -> str:
    """The letter. Every bar comes from the settings block, so the ladder is inspectable."""
    cfg = clean(settings) if settings is not None else clean(None)
    if (coverage_pct >= cfg["min_coverage_pct"] and biggest_gap_ms <= cfg["gap_a_s"] * 1000
            and stale_ms <= cfg["stale_a_s"] * 1000 and duplicates_extra == 0
            and out_of_order == 0):
        return "A"
    if (coverage_pct >= cfg["warn_coverage_pct"] and biggest_gap_ms <= cfg["gap_b_s"] * 1000
            and stale_ms <= cfg["stale_b_s"] * 1000 and duplicates_extra <= cfg["dup_b"]
            and out_of_order <= cfg["order_b"]):
        return "B"
    if coverage_pct >= cfg["low_coverage_pct"] and stale_ms <= cfg["stale_b_s"] * 1000:
        return "C"
    if coverage_pct >= cfg["floor_coverage_pct"]:
        return "D"
    return "F"


def _join_and(parts: list[str]) -> str:
    """Plain-English list joining: "A and B", "A, B and C"."""
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def sentence_for(row: dict[str, Any]) -> str:
    """The one plain sentence: coverage, then the largest gap, then the stamp problems.

    "history for BTCUSDT is 96% complete over the last 24 h; the largest gap is 4 m 12 s at 03:12 and
    there were 3 duplicate stamps"
    """
    symbol = str(row.get("symbol") or "?")
    coverage = fmt_pct(row.get("coverage_pct"))
    window = fmt_window(row.get("window_s"))
    parts = [f"history for {symbol} is {coverage}% complete over the last {window}"]
    tail: list[str] = []
    biggest = row.get("biggest_gap") or {}
    if biggest:
        tail.append(f"the largest gap is {fmt_duration(biggest.get('gap_ms'))} "
                    f"at {fmt_clock(biggest.get('from_ms'))}")
    extra = int((row.get("duplicates") or {}).get("extra") or 0)
    if extra:
        tail.append(f"there were {extra} duplicate stamp{'s' if extra != 1 else ''}")
    backwards = int((row.get("out_of_order") or {}).get("n") or 0)
    if backwards:
        tail.append(f"{backwards} stamp{'s' if backwards != 1 else ''} arrived out of order")
    stale_ms = int(row.get("stale_ms") or 0)
    if stale_ms > 0 and not row.get("fresh", True):
        tail.append(f"nothing has arrived for {fmt_duration(stale_ms)}")
    listed = int(row.get("n_gaps") or 0)
    total = int(row.get("n_gaps_total") or listed)
    if total > 1:
        tail.append(f"{total} gaps in all" + (f" (the {listed} biggest are listed)"
                                              if total > listed else ""))
    if row.get("capped"):
        tail.append("the read was capped")
    if tail:
        return parts[0] + "; " + _join_and(tail)
    return parts[0]


#: Worst first — the panel's own order, mirrored: F..A, a letter this build cannot read leads them
#: all, and the thinnest coverage breaks a tie (§148 T5-F-07).
_VERDICT_RANK = {"F": 0, "D": 1, "C": 2, "B": 3, "A": 4}


def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Worst first — the list leads with what to fix (§148 T5-F-07: the server sorted
    best-first while the panel and its test said worst-first, and the test passed by accident).
    """
    rows.sort(key=lambda row: (_VERDICT_RANK.get(str(row.get("verdict") or "").upper(), -1),
                               float(row.get("coverage_pct") or 0.0)))
    return rows


def repairs_for(row: dict[str, Any], settings: Optional[dict[str, Any]] = None,
                sample_cap: Any = None) -> list[dict[str, Any]]:
    """What the app can do about what the scorecard found — in the order worth doing it.

    Each hint is ``{action, label, why, available, route, symbol}``. ``available`` is the honest
    half: the two repairs with a real route are marked so, and the two this build has no path for
    (dropping duplicate rows, resorting the table) say that instead of offering a dead button.
    """
    cfg = clean(settings) if settings is not None else clean(None)
    symbol = str(row.get("symbol") or "")
    coverage = float(row.get("coverage_pct") or 0.0)
    hints: list[dict[str, Any]] = []

    stale_ms = int(row.get("stale_ms") or 0)
    if coverage < cfg["min_coverage_pct"] or stale_ms > cfg["stale_a_s"] * 1000:
        hints.append({
            "action": "refetch", "label": f"refetch {symbol} for the days the archive still serves",
            "why": ("the venue's public archive keeps past days, so re-reading them fills what the "
                    "store missed; it does not publish today or the future, so a stale head waits "
                    "for the feed"),
            "available": True, "route": ROUTE_BACKFILL, "symbol": symbol,
        })
    gaps = row.get("gaps") or []
    if gaps:
        biggest = gaps[0]
        total = int(row.get("n_gaps_total") or len(gaps))
        hints.append({
            "action": "backfill",
            "label": (f"backfill the {fmt_duration(biggest.get('gap_ms'))} hole from "
                      f"{biggest.get('from_utc')} UTC"),
            "why": f"{total} gap(s) in this window; the biggest is the one to fix first",
            "available": True, "route": ROUTE_BACKFILL, "symbol": symbol,
        })
    extra = int((row.get("duplicates") or {}).get("extra") or 0)
    if extra:
        hints.append({
            "action": "dedupe", "label": f"drop {extra} duplicate stamp{'s' if extra != 1 else ''}",
            "why": ("a duplicate is the same print stored twice; the read keys on the timestamp so "
                    "studies are not double-counted, but no route in this build deletes the rows"),
            "available": False, "route": "", "symbol": symbol,
        })
    backwards = int((row.get("out_of_order") or {}).get("n") or 0)
    if backwards:
        hints.append({
            "action": "order", "label": f"resort {backwards} out-of-order stamp(s)",
            "why": ("every read orders by timestamp, so the studies are already safe; this is the "
                    "stored order, and no route in this build rewrites it"),
            "available": False, "route": "", "symbol": symbol,
        })
    if int(row.get("future_n") or 0) > 0:
        hints.append({
            "action": "clock", "label": "check the source clock",
            "why": (f"{int(row['future_n'])} stamp(s) are dated in the future — a venue clock or an "
                    "import with the wrong zone, and nothing here can fix that guesswork"),
            "available": False, "route": "", "symbol": symbol,
        })
    if row.get("capped"):
        # §148 T5-F-11/F-12: the advice has to be reachable and honest — the window is the
        # user's setting (there is no hours/kind/symbols control on the panel), and a retention
        # prune trims the OLD end while this read counts from the newest one, so a prune cannot
        # uncap it either.
        hints.append({
            "action": "trim",
            "label": "shorten the quality window (Settings ▸ Data quality ▸ Data-quality window)",
            "why": (f"the read is capped at {int(sample_cap or cfg['max_samples'])} samples, and "
                    f"more rows than that arrived in "
                    f"{fmt_window(row.get('configured_window_s'))} — a shorter window fits in "
                    f"one read; a retention prune trims the old end, and this read counts from "
                    f"the newest one, so pruning cannot uncap it"),
            "available": False, "route": "", "symbol": symbol,
        })
    return hints


def refusal(symbol: Any, *, kind: str = "", asset_class: str = "") -> dict[str, Any]:
    """The polite no: a symbol with nothing stored gets a sentence, never a zero-filled scorecard."""
    sym = str(symbol or "").strip().upper() or "(none)"
    words = f"no stored history for {sym} yet — open a chart and let it load"
    return {"ok": False, "symbol": sym, "detail": words, "error": words,
            "kind": str(kind or ""), "asset_class": str(asset_class or ""),
            "verdict": "", "coverage_pct": 0.0, "sentence": words, "gaps": [], "repairs": []}


def scorecard(symbol: Any, samples: Optional[Iterable[Any]] = None, *, asset_class: str = "",
              kind: str = "", now_ms: Optional[int] = None, settings: Optional[Any] = None,
              window_h: Optional[float] = None, capped: bool = False, count: Any = None,
              first_ms: Any = None, last_ms: Any = None,
              sample_cap: Any = None) -> dict[str, Any]:
    """One instrument's data-quality scorecard. Pure: timestamps in, plain dict out, never raises.

    ``samples`` is anything carrying a stamp — ints, ``{"ts_ms": …}`` dicts, Tick/Candle objects.
    When there are no stamps but a ``count``/``first_ms``/``last_ms`` summary is given, the reading
    is a coarse one (coverage and staleness, no gap list) and says so in ``notes``.

    The judged window is ``window_h`` back from ``now_ms`` — but never earlier than the first row the
    caller actually read (``capped``), because a scorecard may only judge what it looked at.
    """
    cfg = clean(settings)
    now = _epoch_ms(now_ms, int(time.time() * 1000))
    series = str(kind or cfg["kind"]).strip().lower()
    series = series if series in ("ticks", "candles") else "ticks"
    klass = str(asset_class or "").strip().lower()
    klass = klass if klass in CLASSES else DEFAULT_CLASS
    sym = str(symbol or "").strip().upper() or "?"

    stamps = [stamp for stamp in (to_timestamp(s) for s in _as_list(samples)) if stamp > 0]
    try:
        given_count = int(count) if count is not None else 0
    except (TypeError, ValueError, OverflowError):
        given_count = 0
    sparse = (not stamps) and (given_count > 0 or bool(first_ms) or bool(last_ms))
    if not stamps and not sparse:
        return refusal(sym, kind=series, asset_class=klass)

    cadence = cadence_ms_for(klass, series, cfg)
    try:
        wanted_ms = int((window_h if window_h is not None else cfg["window_h"]) * 3_600_000)
    except (TypeError, ValueError, OverflowError):
        wanted_ms = int(cfg["window_h"] * 3_600_000)
    configured_ms = max(cadence * 2, wanted_ms)
    raw_from = now - configured_ms

    if sparse:
        first = to_timestamp(first_ms) or now
        last = to_timestamp(last_ms) or first
        stamp_count = given_count
        window_from = raw_from
        covered_ms = max(cadence, now - window_from)
        present_slots = int(stamp_count)
        gaps: list[dict[str, Any]] = []
        holes = 0
        gaps_total = 0
        duplicates = {"n": 0, "extra": 0, "first_ms": 0}
        disorder = {"n": 0, "first_ms": 0}
        future_n = 0
        distinct = stamp_count
    else:
        future_cut = now + cadence
        # The stamp problems are measured in the order the caller passed them (that is what a
        # stored-order problem IS); the coverage and the gaps are measured on the sorted set.
        raw_window = [stamp for stamp in stamps if raw_from <= stamp <= future_cut]
        future_n = sum(1 for stamp in stamps if stamp > future_cut)
        in_window = sorted(raw_window)
        if not in_window:
            return refusal(sym, kind=series, asset_class=klass)
        stamp_count = len(in_window)
        distinct = len(set(in_window))
        first, last = in_window[0], in_window[-1]
        # A capped read may only judge the rows it actually took; an uncapped one judged the whole
        # window it asked for, so a hole at the head of the window counts as missing coverage (there
        # is no left-hand stamp to bracket it, so it shows up in the percentage, not in the gaps).
        window_from = max(raw_from, first) if capped else raw_from
        covered_ms = max(cadence, now - window_from)
        present_slots = len({(stamp - window_from) // cadence for stamp in in_window})
        slots, holes, gaps_total = detect_gaps(
            in_window, cadence, min_slots=int(cfg["gap_mult"]),
            merge_present=int(cfg["merge_present"]), keep=int(cfg["keep_gaps"]))
        gaps = slots
        duplicates = count_duplicates(raw_window)
        disorder = count_disorder(raw_window)

    factor = session_factor(window_from, now, klass, cfg)
    expected_slots = max(1, int(round(covered_ms / cadence * factor)))
    coverage = min(100.0, round(100.0 * present_slots / expected_slots, 1))
    stale_ms = max(0, now - last)
    fresh_ms = fresh_window_ms("candles" if series == "candles" else "trades")
    fresh = bool(last) and stale_ms <= fresh_ms

    biggest_gap = gaps[0] if gaps else None
    row: dict[str, Any] = {
        "ok": True,
        "symbol": sym, "asset_class": klass, "kind": series,
        "verdict": "F", "verdict_note": "", "sentence": "",
        "coverage_pct": coverage,
        "present_slots": present_slots, "expected_slots": expected_slots,
        "missing_slots": max(0, expected_slots - present_slots),
        "samples": stamp_count, "distinct_samples": distinct,
        "cadence_ms": cadence,
        "configured_window_ms": configured_ms, "window_ms": covered_ms,
        "window_s": int(covered_ms // 1000),
        "configured_window_s": int(configured_ms // 1000),
        "window_from_ms": window_from, "window_to_ms": now,
        "first_ms": first, "last_ms": last,
        "history_span_ms": max(0, last - first),
        "history_share_pct": round(
            min(100.0, 100.0 * max(cadence, last - first + cadence) / configured_ms), 1),
        "stale_ms": stale_ms, "fresh": fresh, "fresh_window_ms": fresh_ms,
        "gaps": gaps, "n_gaps": len(gaps), "n_gaps_total": gaps_total, "n_holes": holes,
        "biggest_gap": biggest_gap,
        "duplicates": duplicates, "out_of_order": disorder, "future_n": future_n,
        "session_factor": round(factor, 4), "session_note": session_note(klass, cfg),
        "capped": bool(capped), "coarse": sparse, "notes": [], "repairs": [],
    }

    row["verdict"] = verdict_for(
        coverage_pct=coverage,
        biggest_gap_ms=int(biggest_gap["gap_ms"]) if biggest_gap else 0,
        stale_ms=stale_ms, duplicates_extra=int(duplicates["extra"]),
        out_of_order=int(disorder["n"]), settings=cfg)

    notes: list[str] = []
    if capped and row["verdict"] == "A":
        # An A claims the whole window was read. A capped read cannot make that claim, so the letter
        # drops to B and says why — the alternative is a clean letter over a window nobody looked at.
        row["verdict"] = "B"
        notes.append("the read was capped, so the window was judged only in part — the clean letter "
                     "needs a full read (a shorter window, or a bigger read cap)")
    row["verdict_note"] = VERDICT_NOTES.get(row["verdict"], "")

    if sparse:
        notes.append("read from a count only — no spacings were read, so there is no gap list here")
    if capped:
        # The cap that bit is the read's own budget (the shared cap split across the instruments,
        # §148 T5-F-06) — quoting the whole-store setting told 24 instruments they had 60 000.
        notes.append(f"the read stopped at {int(sample_cap or cfg['max_samples'])} samples, so "
                     f"this covers the {fmt_window(row['window_s'])} the read could take from "
                     f"the newest end")
    if row["history_share_pct"] < 99.0 and not capped:
        notes.append(f"the store holds {fmt_window(row['window_s'])} of history inside the "
                     f"{fmt_window(row['configured_window_s'])} window")
    if row["session_note"]:
        notes.append(row["session_note"])
    if holes:
        notes.append(f"{holes} hole(s) shorter than {cfg['gap_mult']} cadence step(s) — counted, "
                     f"not listed")
    if not row["fresh"] and stale_ms > 0:
        notes.append(f"the newest sample is {fmt_duration(stale_ms)} old (the live chips call a "
                     f"{'candle' if series == 'candles' else 'trade'} stale past "
                     f"{fmt_duration(fresh_ms)})")
    row["notes"] = notes
    row["sentence"] = sentence_for(row)
    row["repairs"] = repairs_for(row, cfg, sample_cap=sample_cap)
    return row


def row_of(card: dict[str, Any], *, keep_gaps: int = 3) -> dict[str, Any]:
    """One scorecard squeezed to what a cockpit row needs (the detail keeps the full gap list)."""
    if not card.get("ok"):
        return {"ok": False, "symbol": card.get("symbol", ""), "detail": card.get("detail", ""),
                "error": card.get("error", ""), "verdict": "", "coverage_pct": 0.0,
                "sentence": card.get("sentence", ""), "gaps": [], "repairs": []}
    return {
        "ok": True, "symbol": card["symbol"], "asset_class": card["asset_class"],
        "kind": card["kind"], "verdict": card["verdict"], "verdict_note": card["verdict_note"],
        "sentence": card["sentence"], "coverage_pct": card["coverage_pct"],
        "samples": card["samples"], "present_slots": card["present_slots"],
        "expected_slots": card["expected_slots"], "window_s": card["window_s"],
        "configured_window_s": card["configured_window_s"], "capped": card["capped"],
        "stale_ms": card["stale_ms"], "fresh": card["fresh"],
        "n_gaps": card["n_gaps"], "n_holes": card["n_holes"],
        "biggest_gap": card["biggest_gap"],
        "duplicates": card["duplicates"], "out_of_order": card["out_of_order"],
        "gaps": list(card["gaps"])[:max(0, int(keep_gaps))],
        "repairs": list(card["repairs"]),
    }


# ══════════════════════════════════════════════════════════════
# The route — the only part that touches SQLite
# ══════════════════════════════════════════════════════════════

async def _open_db() -> tuple[Any, bool]:
    """(handle, close_it) — the running engine's own DB handle when there is one, else a fresh one.

    The read-only-ish fallback mirrors ``desktop/api.py``'s stored-trade route: a ``Database`` opened
    and closed around the read. A missing database file is reported as no handle at all, because a
    panel is not allowed to create (or connect to) a store that is not there.
    """
    from orderflow_system.data.database import Database
    from orderflow_system.desktop import config_store

    try:
        from orderflow_system.desktop import engine as engine_mod
        system = getattr(engine_mod.engine, "system", None) or getattr(engine_mod.engine, "_system", None)
        live = getattr(system, "db", None) if system is not None else None
    except Exception:                                      # noqa: BLE001 — the engine may be stopped
        live = None
    if live is not None:
        return live, False
    path = Path(config_store.db_path())
    if not path.exists():
        return None, False
    db = Database(str(path))
    await db.connect()
    return db, True


async def _read_stamps(db: Any, symbol: str, kind: str, timeframe: str, start_ms: int,
                       end_ms: int, limit: int) -> tuple[list[int], bool]:
    """The stored stamps of one instrument, newest end first, capped at ``limit`` — plus whether the
    cap was hit.

    Ticks go through ``Database.get_recent_ticks`` (the stored-trade read the app already ships);
    candles through ``Database.get_candles``. Both are the app's own accessors, so the cockpit sees
    exactly the rows a study would.
    """
    limit = max(2, int(limit))
    if str(kind) == "candles":
        rows = await db.get_candles(symbol, str(timeframe or "1m"), int(start_ms), int(end_ms))
        stamps = sorted(stamp for stamp in (to_timestamp(row) for row in (rows or [])) if stamp > 0)
        capped = len(stamps) > limit
        return (stamps[-limit:] if capped else stamps), capped
    # One past the budget: a store holding exactly the budget read the window in full, while one
    # that hands back more was truncated by the read (§148 T5-F-05 — `>=` called the former
    # capped and dropped a clean A to B).
    rows = await db.get_recent_ticks(symbol, int(start_ms), int(end_ms), limit=limit + 1)
    stamps = sorted(stamp for stamp in (to_timestamp(row) for row in (rows or [])) if stamp > 0)
    capped = len(stamps) > limit
    return (stamps[-limit:] if capped else stamps), capped


async def _configured_instruments() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """The cockpit's own list: the config's enabled instruments, plus the symbol → asset class table."""
    from orderflow_system.desktop import config_store

    try:
        cfg = config_store.load_config()
    except Exception:                                      # noqa: BLE001 — a broken config is a sentence
        logger.debug("data quality: config read failed", exc_info=True)
        return [], {}
    rows = [row for row in (cfg.get("instruments") or []) if isinstance(row, dict)]
    table = {str(row.get("symbol") or "").upper(): str(row.get("asset_class") or "")
             for row in rows if row.get("symbol")}
    explicit = dict(getattr(config_store, "ASSET_CLASS", {}) or {})
    merged = {**{k.upper(): v for k, v in explicit.items()}, **table}
    enabled = [row for row in rows if row.get("enabled", True)]
    return (enabled or rows), merged


async def _stored_instruments(db: Any) -> list[str]:
    """Instruments the store itself holds rows for — the fallback list when nothing is enabled."""
    try:
        names = await db.tick_instruments()
    except Exception:                                      # noqa: BLE001 — a read failure is not fatal
        return []
    return [str(name).upper() for name in (names or []) if str(name or "").strip()]


@router.get("/data-quality")
async def data_quality_rows(symbols: str = Query(default=""), hours: float = Query(default=0.0),
                            kind: str = Query(default="")) -> dict[str, Any]:
    """One scorecard row per instrument — the cockpit's list.

    ``symbols`` is a comma-separated override; empty means the config's own enabled instruments (and,
    when none are enabled, whatever the tick store holds). ``hours`` overrides the row window
    (``rows_window_h``), ``kind`` the stored series (ticks|candles). The read budget is shared: each
    instrument may take ``max_samples / instruments`` rows, and a row that hit its cap says so.
    """
    from orderflow_system.desktop import config_store

    settings = clean(None)
    try:
        cfg = config_store.load_config()
        settings = clean(cfg.get("data_quality") if isinstance(cfg, dict) else None)
    except Exception:                                      # noqa: BLE001 — defaults stand
        logger.debug("data quality: config read failed, defaults stand", exc_info=True)

    series = str(kind or settings["kind"]).strip().lower()
    series = series if series in ("ticks", "candles") else "ticks"
    span_h = float(hours) if float(hours or 0) > 0 else float(settings["rows_window_h"])
    now = int(time.time() * 1000)

    wanted = [sym.strip().upper() for sym in str(symbols or "").split(",") if sym.strip()]
    table: dict[str, str] = {}
    if not wanted:
        configured, table = await _configured_instruments()
        wanted = [sym for sym in (str(row.get("symbol") or "").upper() for row in configured) if sym]

    db, close_it = await _open_db()
    try:
        if not wanted and db is not None:
            wanted = await _stored_instruments(db)
        wanted = wanted[:int(settings["max_symbols"])]
        if not wanted:
            return {"ok": False, "detail": "no instruments to check yet — enable one in Instruments "
                                           "and let the engine store some history",
                    "error": "no instruments to check yet — enable one in Instruments and let the "
                             "engine store some history",
                    "rows": [], "count": 0, "at": now, "kind": series, "window_h": span_h}
        budget = max(2_000, int(settings["max_samples"]) // max(1, len(wanted)))
        rows: list[dict[str, Any]] = []
        for sym in wanted:
            klass = infer_asset_class(sym, table)
            try:
                start = now - int(span_h * 3_600_000)
                stamps, capped = await _read_stamps(db, sym, series, settings["timeframe"], start,
                                                    now, budget)
            except Exception:                              # noqa: BLE001 — one symbol never sinks the list
                logger.debug("data quality: read failed for %s", sym, exc_info=True)
                stamps, capped = [], False
            card = scorecard(sym, stamps, asset_class=klass, kind=series, now_ms=now,
                             settings=settings, window_h=span_h, capped=capped,
                             sample_cap=budget)
            rows.append(row_of(card))
        # Worst first — the panel's own order, through the one shared ranking. This line used to
        # sort by the raw letter ("A" < "F"), so the cockpit's list opened with the healthiest
        # instrument while the panel re-sorted its rows the other way (T5-F-07).
        rows = sort_rows(rows)
        return {"ok": True, "at": now, "kind": series, "window_h": span_h,
                "settings": settings, "count": len(rows), "rows": rows,
                "note": ("the read walks backwards from the newest sample and stops at the cap, so a "
                         "row that hit it says so") if series == "ticks"
                        else f"one closed {settings['timeframe']} bar per point"}
    finally:
        if close_it and db is not None:
            try:
                await db.close()
            except Exception:                              # pragma: no cover - defensive
                logger.debug("data quality: db close failed", exc_info=True)


@router.get("/data-quality/{symbol}")
async def data_quality_symbol(symbol: str, hours: float = Query(default=0.0),
                              kind: str = Query(default="")) -> dict[str, Any]:
    """One instrument's full scorecard: coverage, the gap list, duplicates, staleness, verdict, and
    the repairs the app can run. A symbol with nothing stored answers the refusal sentence."""
    from orderflow_system.desktop import config_store

    sym = str(symbol or "").strip().upper()
    settings = clean(None)
    table: dict[str, str] = {}
    try:
        cfg = config_store.load_config()
        settings = clean(cfg.get("data_quality") if isinstance(cfg, dict) else None)
        table = {str(row.get("symbol") or "").upper(): str(row.get("asset_class") or "")
                 for row in (cfg.get("instruments") or []) if isinstance(row, dict)}
        table = {**{k.upper(): v for k, v in (getattr(config_store, "ASSET_CLASS", {}) or {}).items()},
                 **table}
    except Exception:                                      # noqa: BLE001 — defaults stand
        logger.debug("data quality: config read failed, defaults stand", exc_info=True)

    if not sym:
        return {"ok": False, "detail": "name an instrument — the scorecard is about one symbol",
                "error": "name an instrument — the scorecard is about one symbol"}
    series = str(kind or settings["kind"]).strip().lower()
    series = series if series in ("ticks", "candles") else "ticks"
    klass = infer_asset_class(sym, table)
    span_h = float(hours) if float(hours or 0) > 0 else float(settings["window_h"])
    now = int(time.time() * 1000)

    db, close_it = await _open_db()
    try:
        if db is None:
            return refusal(sym, kind=series, asset_class=klass)
        try:
            stamps, capped = await _read_stamps(db, sym, series, settings["timeframe"],
                                                now - int(span_h * 3_600_000), now,
                                                settings["max_samples"])
        except Exception:                                  # noqa: BLE001 — a read failure is a sentence
            logger.debug("data quality: read failed for %s", sym, exc_info=True)
            stamps, capped = [], False
        card = scorecard(sym, stamps, asset_class=klass, kind=series, now_ms=now,
                         settings=settings, window_h=span_h, capped=capped)
        if card.get("ok"):
            card["settings"] = settings
        return card
    finally:
        if close_it and db is not None:
            try:
                await db.close()
            except Exception:                              # pragma: no cover - defensive
                logger.debug("data quality: db close failed", exc_info=True)
