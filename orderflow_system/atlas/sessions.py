"""Session templates and the futures roll calendar — when a market is open, and when the contract moves.

`freshness.py` answers "how old is this sample". This module answers the two questions every other
panel quietly assumes: *is this market open right now*, and *how long until the chart has to be on a
different contract*. Neither answer is data — both are arithmetic over conventions — which is exactly
why they live here, in pure functions with an injectable clock, instead of in a feed handler.

WHAT A TEMPLATE IS
------------------
A template is a plain dict: a name, a timezone, the weekdays it trades, an open and a close, optional
intraday breaks, holiday dates, and an optional exchange label.

    {"name": "us-equities-rth", "timezone": "America/New_York", "days": "mon-fri",
     "open": "09:30", "close": "16:00", "holiday_rule": "us-market",
     "breaks": [{"start": "12:00", "end": "13:00"}],
     "holidays": [{"date": "2026-11-27", "name": "day after Thanksgiving", "closed": False,
                   "close": "13:00"}],
     "exchange": "NYSE / Nasdaq", "symbols": ["SPY", "QQQ"]}

`BUILTINS` is a small library of sensible ones — crypto 24/7, US equities regular hours plus both
extended sessions, the CME Globex hours for the index, energy and metal contracts, Tokyo's two-part
day (a break example), and the Sydney / London / New York FX centres. They are examples: copy one,
rename it, change the times. Each is documented in `note`, which the panel prints.

THE ZONE LAYER IS BUILT IN, NOT FETCHED
---------------------------------------
Zone rules are a table (below) rather than a tz database import: the majors a trading desk needs, each
with its standard offset and, where it applies, its DST rule — US (second Sunday in March to first
Sunday in November), EU (last Sunday in March to last Sunday in October), Sydney (first Sunday in
October to first Sunday in April). This keeps the module stdlib-only and its DST behaviour pinned by
tests at chosen instants instead of depending on whichever tzdata a host happens to ship. A zone the
table does not know is kept as written, flagged (`timezone_known: False`), read as UTC, and named in
`validate()` — a template must never silently lie twice a year.

A session may WRAP midnight (Globex opens 17:00 CT and closes 16:00 CT the next day), so a session
belongs to the local day it OPENED, and `open_ms`/`close_ms` are the stamps of the running session,
not of the calendar day. Real elapsed time comes from those stamps (so a DST transition inside a
session cannot corrupt them); the wall clock comes from the zone table (so breaks and phases read the
way the screen reads).

THE ROLL CALENDAR IS DOCUMENTED CONVENTION, NOT A DATA FEED
-----------------------------------------------------------
* **equity index** (ES, NQ, YM, RTY and their micros): the contract expires on the **third Friday** of
  its month, quarterly cycle (H, M, U, Z). ES settles on that Friday's *open*, so the front month's
  last full trading day is the Thursday before — that is the roll date here.
* **energy** (CL, NG, RB, HO): the contract expires **three business days before the 25th** of the
  month preceding delivery, every month — the CME convention. The front month's volume migrates
  ahead of the last trading day, so the roll date here is three business days before expiry.
* **metals** (GC, SI, HG): trading terminates on the **third-to-last business day** of the contract
  month, every month; the roll date is the business day before that.
* **perpetuals** (BTC, ETH, SOL): there is no roll. The scheduled event is funding, every eight hours
  at 00:00, 08:00 and 16:00 UTC, and that is what the table answers with.

A business day here is Monday–Friday: the module does not carry an exchange holiday calendar for the
roll arithmetic (the session templates carry the holidays a desk actually looks at, and the two
questions are separate). The energy family's own non-business-day clause is honoured — a 25th that
lands on a weekend starts the count-back from the Friday — but where a *holiday* moves a real expiry
by a day, the row is off by that day — said plainly rather than papered over.

`clean()` never raises: unknown keys are dropped, wrong types are defaulted, a number outside its
bounds is clamped, and a non-finite number (the `Infinity` a JSON file can carry) reads as
unreadable rather than taking the read down. Every pure function takes `now_ms`; nothing here reads a clock, a file or a socket.

The panel reads one route:

    GET /api/atlas/sessions                  the active template's clock + the roll table
    GET /api/atlas/sessions?symbol=ESZ26     the template that symbol belongs to
    GET /api/atlas/sessions?template=fx-sydney
    GET /api/atlas/sessions?root=CL&months=8
"""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/atlas", tags=["atlas"])

MINUTE_MS = 60_000
MINUTES_PER_DAY = 1440
DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

#: The clock's own bounds. `session_state` is called with whatever a caller has — a missing clock, a
#: NaN, a timestamp from a broken feed — and a value outside the calendar's range would raise inside
#: datetime. Clamping keeps the panel answering (the epoch and the far end of the calendar are both
#: "closed"). The upper bound is not `date.max`: `next_session` searches a fortnight ahead of the
#: clock, and a clock sitting on the last day would walk off the end of the calendar and raise.
CLOCK_MIN_MS = 0
_HORIZON_DAYS = 15
CLOCK_MAX_MS = ((datetime(9999, 12, 31) - timedelta(days=_HORIZON_DAYS)) -
                datetime(1970, 1, 1)) // timedelta(milliseconds=1)


def _clock(value: Any) -> int:
    """A usable millisecond clock from anything at all.

    A non-finite float — the hand-edited `Infinity` a JSON file can carry, `1e999` in a POSTed
    body — raises OverflowError out of `int()`. It reads as "no usable clock" like every other
    junk value: the panel answering is the contract (`clean()` never raises).
    """
    try:
        moment = int(value)
    except (TypeError, ValueError, OverflowError):
        moment = 0
    return max(CLOCK_MIN_MS, min(CLOCK_MAX_MS, moment))

# ── the zone table ──────────────────────────────────────────────────────────────────────────────
#: Standard offset in minutes, the DST offset when the rule applies, and which rule (us | eu | au).
#: A zone with no rule (Japan, Hong Kong, India, ...) is a fixed offset and always will be.
ZONES: dict[str, dict[str, Any]] = {
    "UTC": {"offset": 0},
    "America/New_York": {"offset": -300, "dst": -240, "rule": "us"},
    "America/Chicago": {"offset": -360, "dst": -300, "rule": "us"},
    "America/Denver": {"offset": -420, "dst": -360, "rule": "us"},
    "America/Los_Angeles": {"offset": -480, "dst": -420, "rule": "us"},
    "America/Sao_Paulo": {"offset": -180},
    "Europe/London": {"offset": 0, "dst": 60, "rule": "eu"},
    "Europe/Berlin": {"offset": 60, "dst": 120, "rule": "eu"},
    "Europe/Zurich": {"offset": 60, "dst": 120, "rule": "eu"},
    "Europe/Paris": {"offset": 60, "dst": 120, "rule": "eu"},
    "Asia/Tokyo": {"offset": 540},
    "Asia/Hong_Kong": {"offset": 480},
    "Asia/Shanghai": {"offset": 480},
    "Asia/Singapore": {"offset": 480},
    "Asia/Kolkata": {"offset": 330},
    "Asia/Dubai": {"offset": 240},
    "Australia/Sydney": {"offset": 600, "dst": 660, "rule": "au"},
    "Australia/Melbourne": {"offset": 600, "dst": 660, "rule": "au"},
}

#: The names a user is likely to type instead of the canonical one.
ZONE_ALIASES: dict[str, str] = {
    "utc": "UTC", "gmt": "UTC", "z": "UTC", "universal": "UTC",
    "us/eastern": "America/New_York", "new york": "America/New_York", "ny": "America/New_York",
    "us/central": "America/Chicago", "chicago": "America/Chicago", "ct": "America/Chicago",
    "us/mountain": "America/Denver", "us/pacific": "America/Los_Angeles",
    "los angeles": "America/Los_Angeles", "pt": "America/Los_Angeles",
    "london": "Europe/London", "berlin": "Europe/Berlin", "frankfurt": "Europe/Berlin",
    "zurich": "Europe/Zurich", "paris": "Europe/Paris",
    "tokyo": "Asia/Tokyo", "japan": "Asia/Tokyo", "hong kong": "Asia/Hong_Kong",
    "shanghai": "Asia/Shanghai", "singapore": "Asia/Singapore", "kolkata": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata", "dubai": "Asia/Dubai",
    "sydney": "Australia/Sydney", "melbourne": "Australia/Melbourne",
}


def canonical_zone(name: Any) -> str:
    """The table's own name for a zone, or "" when the table does not know it."""
    text = str(name or "").strip()
    if not text:
        return ""
    if text in ZONES:
        return text
    lower = text.lower()
    if lower in ZONE_ALIASES:
        return ZONE_ALIASES[lower]
    for zone in ZONES:                      # "america/new_york" and other case slips
        if zone.lower() == lower:
            return zone
    return ""


def zone_known(name: Any) -> bool:
    return bool(canonical_zone(name))


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th `weekday` (Monday=0) of a month — 2nd Sunday of March, 3rd Friday of December."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    first_next = date(year + (month == 12), (month % 12) + 1, 1)
    last = first_next - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


#: The epoch. Every conversion below is arithmetic on it rather than `fromtimestamp`: the OS
#: timestamp range is narrower than datetime's (measured on Windows: the clamped year 9999 raised
#: OSError), and a clock must never be the thing that takes a panel down.
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_ONE_MS = timedelta(milliseconds=1)


def _utc_dt(ms: Any) -> datetime:
    """One instant as a UTC datetime, for the whole range a millisecond clock can name."""
    return _EPOCH + timedelta(milliseconds=int(ms))


def _utc_ms(dt: datetime) -> int:
    return (dt.replace(tzinfo=timezone.utc) - _EPOCH) // _ONE_MS


def _zone_transitions(rule: str, year: int, offset: int = 0, dst: int = 0) -> tuple[int, int]:
    """(DST start, DST end) as UTC stamps for one calendar year.

    Each rule is stated in the zone's OWN wall clock, so a stamp is the wall time minus that zone's
    minutes: the US switches at 02:00 local, which staggers the instant by zone (07:00 UTC Eastern,
    08:00 Central, 09:00 Mountain, 10:00 Pacific), Australia at 02:00 standard / 03:00 DST local
    (= 16:00 UTC the Saturday before, both directions), and the EU at 01:00 UTC for every member —
    the one rule where a single shared instant is the truth. Passing the day alone used to hand every
    US zone the Eastern instant and gave Australia a stamp a day late.
    """
    def wall(day: date, hour: int, minute: int, zone_minutes: int) -> int:
        return _utc_ms(datetime(day.year, day.month, day.day, hour, minute)) - zone_minutes * 60_000

    if rule == "us":
        return (wall(_nth_weekday(year, 3, 6, 2), 2, 0, offset),
                wall(_nth_weekday(year, 11, 6, 1), 2, 0, dst))
    if rule == "eu":
        start = _utc_ms(datetime.combine(_last_weekday(year, 3, 6), datetime.min.time())) + 3600 * 1000
        end = _utc_ms(datetime.combine(_last_weekday(year, 10, 6), datetime.min.time())) + 3600 * 1000
        return start, end
    if rule == "au":
        return (wall(_nth_weekday(year, 10, 6, 1), 2, 0, offset),
                wall(_nth_weekday(year, 4, 6, 1), 3, 0, dst))
    return 0, 0


def zone_offset_minutes(zone: Any, utc_ms: int) -> int:
    """The zone's offset from UTC at one instant, in minutes (negative = west of Greenwich).

    An unknown zone is 0 — the caller has already been told (`zone_known`), and the alternative
    (raising) would take a panel down over a typo.
    """
    spec = ZONES.get(canonical_zone(zone))
    if not spec:
        return 0
    dst = spec.get("dst")
    rule = str(spec.get("rule") or "")
    if dst is None or not rule:
        return int(spec["offset"])
    moment = _clock(utc_ms)
    start, end = _zone_transitions(rule, _utc_dt(moment).year, int(spec.get("offset") or 0), int(dst))
    # The southern hemisphere's season runs across the new year, so its start is later than its end.
    in_dst = (start <= moment < end) if start < end else (moment >= start or moment < end)
    return int(dst if in_dst else spec["offset"])


def local_parts(zone: Any, utc_ms: int) -> dict[str, Any]:
    """One instant as the zone's wall clock: the date, the minute of day, the weekday, the offset."""
    moment = _clock(utc_ms)
    offset = zone_offset_minutes(zone, moment)
    wall = _utc_dt(moment + offset * MINUTE_MS)
    return {
        "zone": canonical_zone(zone) or "UTC",
        "offset_minutes": offset,
        "date": wall.strftime("%Y-%m-%d"),
        "day": wall.day,
        "time": wall.strftime("%H:%M"),
        "minutes": wall.hour * 60 + wall.minute,
        "seconds": wall.second,
        "weekday": wall.weekday(),
        "weekday_name": DAY_NAMES[wall.weekday()],
        "_date": wall.date(),
    }


def _wall_to_utc_ms(zone: Any, wall_ms: int) -> int:
    """A wall-clock stamp (a naive instant read as local time) as the real UTC stamp.

    Two passes: guess the offset at the wall stamp, re-read the offset at the resulting instant, and
    settle. A wall time inside a DST gap resolves to the offset in effect just after it, which is what
    an exchange does with an ambiguous and non-existent 02:00 — and no market opens inside the gap.
    """
    moment = int(wall_ms)
    offset = zone_offset_minutes(zone, moment)
    for _ in range(2):
        settle = zone_offset_minutes(zone, moment - offset * MINUTE_MS)
        if settle == offset:
            break
        offset = settle
    return moment - offset * MINUTE_MS


def _wall_ms(day: date, minutes: int) -> int:
    """A local wall stamp: that date at that minute of day, as a naive instant."""
    return _utc_ms(datetime.combine(day, datetime.min.time())) + int(minutes) * MINUTE_MS


def _as_list(value: Any) -> list[Any]:
    """A list from whatever the config holds: a real list, a tuple, or one scalar."""
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _text(value: Any, limit: int = 120) -> str:
    return str(value if value is not None else "").strip()[:limit]


def _int(value: Any, default: int) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError, OverflowError):     # OverflowError: Infinity, see _clock()
        return default


# ── times, days, holidays ───────────────────────────────────────────────────────────────────────

def parse_minutes(value: Any) -> Optional[int]:
    """A wall-clock time as minutes past local midnight: "09:30", "9:30", "0930", 570, "24:00".

    "24:00" (and 1440) is the end of the day, which is how a 24-hour market is written. An unreadable
    value is None — never 0, because 00:00 is a real time and a typo must not read as midnight.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            whole = int(round(float(value)))
        except (TypeError, ValueError, OverflowError):     # Infinity / NaN: unreadable, never 0
            return None
        return whole if 0 <= whole <= MINUTES_PER_DAY else None
    text = str(value or "").strip()
    if not text:
        return None
    if ":" in text:
        hours, _, minutes = text.partition(":")
        try:
            hour, minute = int(hours), int(minutes or 0)
        except ValueError:
            return None
        total = hour * 60 + minute
        return total if 0 <= total <= MINUTES_PER_DAY and 0 <= minute < 60 else None
    if text.isdigit():
        if len(text) <= 2:
            hour = int(text)
            return hour * 60 if 0 <= hour <= 24 else None
        if len(text) <= 4:
            hour, minute = int(text[:-2]), int(text[-2:])
            total = hour * 60 + minute
            return total if 0 <= total <= MINUTES_PER_DAY and 0 <= minute < 60 else None
    return None


def fmt_minutes(minutes: Any) -> str:
    """Minutes past midnight as "HH:MM" (1440 → "24:00"), clamped rather than raising."""
    whole = _int(minutes, 0)
    whole = max(0, min(MINUTES_PER_DAY, whole))
    return "%02d:%02d" % (whole // 60, whole % 60)


_DAY_WORDS: dict[str, int] = {}
for _index, _name in enumerate(DAY_NAMES, start=1):
    _DAY_WORDS[_name] = _index
    if _name[0] not in ("t", "s"):
        # "t" is tue or thu and "s" is sat or sun: seeding the first letter resolved them by the
        # order the names happened to be added, which made `parse_days("t")` a coin toss (§148
        # T4-F7). An ambiguous letter is unreadable, like any other unreadable token.
        _DAY_WORDS[_name[0]] = _index
    _DAY_WORDS[_name + "day"] = _index
_DAY_WORDS.update({"mo": 1, "tu": 2, "we": 3, "th": 4, "fr": 5, "sa": 6, "su": 7})
_DAY_WORDS.update({"weekday": 0, "weekdays": 0, "business": 0, "everyday": 0, "daily": 0,
                   "247": 0, "24/7": 0, "all": 0, "sun-sat": 0})


def parse_days(value: Any) -> list[int]:
    """Weekdays as ISO numbers (Mon=1 … Sun=7).

    Accepts names, abbreviations, numbers, and ranges: "mon-fri", "mon,wed,fri", "1-5", "sun-thu",
    ["mon", "tue"], 5. 0 means Sunday (the other common convention), and "daily" / "24/7" mean all
    seven. An unreadable value is [] — the caller decides what to do about it, never this function.
    """
    if value is None or value == "":
        return []
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return parse_days([int(value)])
        except (TypeError, ValueError, OverflowError):     # Infinity / NaN: unreadable, like any word
            return []
    tokens: list[str] = []
    for item in _as_list(value):
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            try:
                tokens.append(str(int(item)))
            except (TypeError, ValueError, OverflowError):     # Infinity / NaN: no day it could mean
                pass
            continue
        text = str(item or "").lower()
        text = text.replace("–", "-").replace("—", "-").replace(" to ", "-").replace(",", " ")
        tokens.extend(part for part in text.split() if part)
    out: set[int] = set()
    for token in tokens:
        if token in _DAY_WORDS:
            word = _DAY_WORDS[token]
            out.update(range(1, 8) if word == 0 else [word])
            continue
        if "-" in token:
            left, _, right = token.partition("-")
            start, end = _day_number(left), _day_number(right)
            if start and end:
                span = range(start, end + 1) if start <= end else list(range(start, 8)) + list(range(1, end + 1))
                out.update(span)
            continue
        number = _day_number(token)
        if number:
            out.add(number)
    return sorted(out)


def _day_number(token: str) -> int:
    if token in _DAY_WORDS:
        word = _DAY_WORDS[token]
        return 7 if word == 0 else word
    if token.isdigit():
        whole = int(token)
        if whole == 0:
            return 7
        if 1 <= whole <= 7:
            return whole
    return 0


def parse_date(value: Any) -> Optional[date]:
    """A calendar date from "YYYY-MM-DD" or "YYYY/MM/DD" (a datetime is taken as its date)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    found = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", text)
    if not found:
        return None
    try:
        return date(int(found.group(1)), int(found.group(2)), int(found.group(3)))
    except ValueError:
        return None


def parse_holidays(value: Any) -> list[dict[str, Any]]:
    """Holiday entries as {date, name, closed, close}.

    Three shapes are accepted, because a config file gets hand-edited: "2026-07-03", the same with
    the name after it ("2026-07-03 Independence Day (observed)"), or a mapping with `date`, `name`,
    `closed` and an optional early `close`. `closed: false` plus a close is an EARLY CLOSE — the day
    trades, it just ends sooner. A close on a `closed` entry is kept as written and reported as
    ignored by `validate()`, rather than silently deleted from the user's file.
    """
    out: dict[str, dict[str, Any]] = {}
    for item in _as_list(value):
        date_text, name, closed, close = "", "", True, ""
        if isinstance(item, Mapping):
            date_text = _text(item.get("date") or item.get("day"), 12)
            name = _text(item.get("name") or item.get("label"), 80)
            closed = bool(item.get("closed", True))
            if item.get("close") is not None:
                parsed = parse_minutes(item.get("close"))
                close = fmt_minutes(parsed) if parsed is not None else ""
        else:
            text = _text(item, 120)
            found = re.match(r"^(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*(.*)$", text)
            if found:
                date_text, name = found.group(1), found.group(2).strip()
        day = parse_date(date_text)
        if day is None:
            continue
        out[day.isoformat()] = {
            "date": day.isoformat(),
            "name": name or day.strftime("%a %d %b %Y"),
            "closed": closed,
            "close": close,
        }
    return [out[key] for key in sorted(out)][:400]


def _observed(day: date) -> date:
    """The NYSE observance rule: a Saturday holiday is kept on the Friday before, a Sunday on Monday."""
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _easter(year: int) -> date:
    """Easter Sunday (anonymous Gregorian computus) — the anchor for Good Friday."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def us_market_holidays(year: int) -> list[dict[str, Any]]:
    """The US equity market's holidays for one year, by rule (never a hardcoded list).

    New Year's Day, MLK Day (3rd Monday of January), Presidents' Day (3rd Monday of February),
    Good Friday, Memorial Day (last Monday of May), Juneteenth, Independence Day, Labor Day (1st
    Monday of September), Thanksgiving (4th Thursday of November) and Christmas — each moved to the
    Friday before or the Monday after when it lands on a weekend, which is the rule the exchanges
    publish, and named "(observed)" when the date moved.
    """
    fixed = [((1, 1), "New Year's Day"), ((6, 19), "Juneteenth"), ((7, 4), "Independence Day"),
             ((12, 25), "Christmas")]
    rows: list[dict[str, Any]] = []
    for (month, day_number), label in fixed:
        actual = date(year, month, day_number)
        observed = _observed(actual)
        rows.append({"date": observed.isoformat(),
                     "name": label if observed == actual else label + " (observed)",
                     "closed": True, "close": ""})
    movable = [(_nth_weekday(year, 1, 0, 3), "Martin Luther King Jr. Day"),
               (_nth_weekday(year, 2, 0, 3), "Presidents' Day"),
               (_easter(year) - timedelta(days=2), "Good Friday"),
               (_last_weekday(year, 5, 0), "Memorial Day"),
               (_nth_weekday(year, 9, 0, 1), "Labor Day"),
               (_nth_weekday(year, 11, 3, 4), "Thanksgiving")]
    for day, label in movable:
        rows.append({"date": day.isoformat(), "name": label, "closed": True, "close": ""})
    return sorted(rows, key=lambda row: row["date"])


#: The named holiday rule sets a template may ask for. Adding one is a function above and a key here.
HOLIDAY_RULES: dict[str, str] = {"us-market": "the US equity market's holiday calendar, by rule"}

#: Memoised rule years — the clock asks for the same year on every tick.
_RULE_CACHE: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}


def holiday_rule_dates(rule: str, years: list[int]) -> list[dict[str, Any]]:
    if str(rule or "") not in HOLIDAY_RULES:
        return []
    rows: dict[str, dict[str, Any]] = {}
    for year in years:
        for row in us_market_holidays(year):
            rows[row["date"]] = dict(row)
    return [rows[key] for key in sorted(rows)]


# ── templates ───────────────────────────────────────────────────────────────────────────────────

def _slug(text: Any) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(text or "").strip().lower()).strip("-")
    return cleaned[:48] or "template"


def parse_breaks(value: Any) -> list[dict[str, Any]]:
    """Intraday breaks as wall-clock windows: "12:00-13:00", "12:00-13:00 lunch" (the trailing
    words are the label), ["12:00", "13:00"], or {start, end}.

    A break is a WALL-CLOCK window (12:00–13:00 is 12:00 on the clock whether the session opened this
    morning or at 17:00 yesterday), which is what makes a wrap-around session's breaks readable. A
    window that ends before it starts is dropped here; whether it lies inside the session is
    `validate()`'s business.
    """
    out: list[dict[str, Any]] = []
    for item in _as_list(value):
        start = end = None
        label = ""
        if isinstance(item, Mapping):
            start, end = parse_minutes(item.get("start")), parse_minutes(item.get("end"))
            label = _text(item.get("label") or item.get("name"), 40)
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            start, end = parse_minutes(item[0]), parse_minutes(item[1])
        elif isinstance(item, str):
            parts = re.split(r"\s*(?:-|–|—|to)\s*", item.strip(), maxsplit=1)
            if len(parts) == 2:
                start, end = parse_minutes(parts[0]), parse_minutes(parts[1])
                if end is None:
                    # "12:00-13:00 lunch" — the words after the end time are the label. The
                    # separator never sits between a time and its label, so the label is peeled
                    # off the end token: its first word is the time, the rest is the label.
                    # (The old `len(parts) == 3` branch was dead: maxsplit=1 cannot yield 3.)
                    word, _, rest = parts[1].strip().partition(" ")
                    end = parse_minutes(word)
                    if end is not None and rest:
                        label = _text(rest, 40)
        if start is None or end is None or end <= start:
            continue
        row: dict[str, Any] = {"start": fmt_minutes(start), "end": fmt_minutes(end)}
        if label:
            row["label"] = label
        out.append(row)
    out.sort(key=lambda row: parse_minutes(row["start"]) or 0)
    return out[:8]


def parse_symbols(value: Any) -> list[str]:
    """The symbols a template answers for: uppercased, deduped, bounded."""
    out: list[str] = []
    for item in _as_list(value):
        text = _text(item, 16).upper()
        if text and text not in out:
            out.append(text)
    return out[:60]


#: Every key a cleaned template carries. Anything else in an incoming dict is dropped.
TEMPLATE_KEYS = ("name", "title", "exchange", "timezone", "days", "open", "close", "breaks",
                 "holidays", "holiday_rule", "symbols", "note")


def clean_template(raw: Any, fallback_name: str = "") -> dict[str, Any]:
    """One template, coerced onto the shape above. Never raises; never loses the user's intent.

    `raw` that is not a mapping yields a valid blank template (UTC, every day, 00:00 → 24:00) so a
    hand-edited config can never take a panel down. A timezone the table does not know is kept as
    written and flagged by `zone_known()`; the schedule is read as UTC and `validate()` says so.
    """
    src: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
    name = _slug(src.get("name") or fallback_name)
    title = _text(src.get("title"), 80) or name.replace("-", " ")
    open_minutes = parse_minutes(src.get("open"))
    close_minutes = parse_minutes(src.get("close"))
    holiday_rule = _text(src.get("holiday_rule"), 24)
    if holiday_rule and holiday_rule not in HOLIDAY_RULES:
        holiday_rule = ""
    return {
        "name": name,
        "title": title,
        "exchange": _text(src.get("exchange"), 60),
        "timezone": _text(src.get("timezone"), 40) or "UTC",
        "days": parse_days(src.get("days")) or [1, 2, 3, 4, 5],
        "open": fmt_minutes(0 if open_minutes is None else open_minutes),
        "close": fmt_minutes(MINUTES_PER_DAY if close_minutes is None else close_minutes),
        "breaks": parse_breaks(src.get("breaks")),
        "holidays": parse_holidays(src.get("holidays")),
        "holiday_rule": holiday_rule,
        "symbols": parse_symbols(src.get("symbols")),
        "note": _text(src.get("note"), 200),
    }


def open_minutes(template: Mapping[str, Any]) -> int:
    parsed = parse_minutes(template.get("open"))
    return 0 if parsed is None else parsed


def close_minutes(template: Mapping[str, Any]) -> int:
    parsed = parse_minutes(template.get("close"))
    return MINUTES_PER_DAY if parsed is None else parsed


def wraps_midnight(template: Mapping[str, Any]) -> bool:
    """True when the close is at or before the open — Globex's 17:00 → 16:00 is the everyday case."""
    return close_minutes(template) <= open_minutes(template)


def session_span_minutes(template: Mapping[str, Any]) -> int:
    """The session's length in minutes, counting a wrap as the end of the next day."""
    start, end = open_minutes(template), close_minutes(template)
    if end > start:
        return end - start
    if end == start:
        return 0                       # nothing at all; validate() flags it
    return end + MINUTES_PER_DAY - start


def break_windows(template: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The breaks that lie inside the session, as wall-clock windows.

    The session's own window decides membership: for a session that does not wrap, a break must sit
    between the open and the close; for one that wraps, it belongs to the evening side (at or after
    the open) or the morning side (at or before the close). Globex's 16:00–17:00 daily gap is
    therefore not a break — it is the gap between two sessions, and the panel shows it as closed.
    """
    start, end = open_minutes(template), close_minutes(template)
    out: list[dict[str, Any]] = []
    for row in parse_breaks(template.get("breaks")):
        break_start = parse_minutes(row["start"])
        break_end = parse_minutes(row["end"])
        if break_start is None or break_end is None or break_end <= break_start:
            continue
        if start < end:
            inside = break_start >= start and break_end <= end
        elif start > end:
            inside = break_start >= start or break_end <= end
        else:
            inside = False
        if not inside:
            continue
        out.append({"start": row["start"], "end": row["end"], "start_minutes": break_start,
                    "end_minutes": break_end})
    return out


def validate(template: Any) -> list[str]:
    """Plain sentences about a template that would misbehave — the panel prints them verbatim.

    Validation is a report, never a gate: a template with problems still answers, because a trader
    looking at a wrong clock is better served than a trader looking at an empty panel.
    """
    tpl = clean_template(template)
    problems: list[str] = []
    if not zone_known(tpl["timezone"]):
        problems.append("the timezone %s is not one this build knows — the schedule is read as UTC"
                        % tpl["timezone"])
    if session_span_minutes(tpl) == 0:
        problems.append("the open and the close are the same time — this session never opens; "
                        "write 00:00 to 24:00 for a market that does not close")
    elif open_minutes(tpl) >= MINUTES_PER_DAY:
        problems.append("the open is at the very end of the day — the session has no evening side")
    for row in parse_breaks(tpl.get("breaks")):
        if not any(window["start"] == row["start"] and window["end"] == row["end"]
                   for window in break_windows(tpl)):
            problems.append("the break %s–%s falls outside the session's own hours"
                            % (row["start"], row["end"]))
    for entry in tpl["holidays"]:
        if entry["closed"] and parse_minutes(entry.get("close")):
            problems.append("the entry for %s is marked closed, so its early close %s is ignored"
                            % (entry["date"], entry["close"]))
        early = parse_minutes(entry.get("close"))
        if early is not None and early <= open_minutes(tpl):
            problems.append("the early close on %s (%s) is at or before the open — the day would "
                            "never trade" % (entry["date"], entry["close"]))
    return problems


# ── the built-in library ────────────────────────────────────────────────────────────────────────

#: The examples a user copies. Each one is chosen to be a real desk's hours, and each `note` says
#: what it is an example OF, so the picker teaches the shape rather than hiding it.
BUILTINS: dict[str, dict[str, Any]] = {
    "crypto-247": {
        "name": "crypto-247",
        "title": "Crypto perpetuals — 24/7",
        "exchange": "Bybit / Binance / OKX",
        "timezone": "UTC",
        "days": "mon-sun",
        "open": "00:00",
        "close": "24:00",
        "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BTC", "ETH", "SOL"],
        "note": "Example: a market with no closing bell — no breaks, no holidays, always open.",
    },
    "us-equities-rth": {
        "name": "us-equities-rth",
        "title": "US equities — regular hours",
        "exchange": "NYSE / Nasdaq",
        "timezone": "America/New_York",
        "days": "mon-fri",
        "open": "09:30",
        "close": "16:00",
        "holiday_rule": "us-market",
        "symbols": ["SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "AMZN"],
        "note": "Example: the regular session with the US holiday rules — copy it for another cash market.",
    },
    "us-equities-pre": {
        "name": "us-equities-pre",
        "title": "US equities — pre-market",
        "exchange": "NYSE / Nasdaq (extended)",
        "timezone": "America/New_York",
        "days": "mon-fri",
        "open": "04:00",
        "close": "09:30",
        "holiday_rule": "us-market",
        "note": "Example: extended hours. It ends exactly where the regular session opens.",
    },
    "us-equities-post": {
        "name": "us-equities-post",
        "title": "US equities — after hours",
        "exchange": "NYSE / Nasdaq (extended)",
        "timezone": "America/New_York",
        "days": "mon-fri",
        "open": "16:00",
        "close": "20:00",
        "holiday_rule": "us-market",
        "note": "Example: the post-market session, and an early close — add a holiday entry with "
                "closed: false and a close time for a half day.",
    },
    "cme-globex-index": {
        "name": "cme-globex-index",
        "title": "CME Globex — equity index",
        "exchange": "CME",
        "timezone": "America/Chicago",
        "days": "sun-thu",
        "open": "17:00",
        "close": "16:00",
        "symbols": ["ES", "NQ", "YM", "RTY", "MES", "MNQ", "MYM", "M2K"],
        "note": "Example: a session that wraps midnight — it belongs to the day it opened, so "
                "Friday's 16:00 close is Thursday's session ending.",
    },
    "cme-globex-energy": {
        "name": "cme-globex-energy",
        "title": "CME Globex — energy",
        "exchange": "NYMEX",
        "timezone": "America/Chicago",
        "days": "sun-thu",
        "open": "17:00",
        "close": "16:00",
        "symbols": ["CL", "NG", "RB", "HO", "MCL"],
        "note": "Example: the same Globex wheel for the energy contracts — pair it with the roll "
                "table for CL.",
    },
    "cme-globex-metals": {
        "name": "cme-globex-metals",
        "title": "CME Globex — metals",
        "exchange": "COMEX",
        "timezone": "America/Chicago",
        "days": "sun-thu",
        "open": "17:00",
        "close": "16:00",
        "symbols": ["GC", "SI", "HG", "MGC", "SIL"],
        "note": "Example: the Globex wheel for gold, silver and copper.",
    },
    "jp-equities": {
        "name": "jp-equities",
        "title": "Tokyo equities — two-part day",
        "exchange": "TSE",
        "timezone": "Asia/Tokyo",
        "days": "mon-fri",
        "open": "09:00",
        "close": "15:00",
        "breaks": [{"start": "11:30", "end": "12:30", "label": "lunch"}],
        "symbols": ["JP225", "NI225"],
        "note": "Example: a session with a real break in the middle — the panel shows break as its "
                "own phase.",
    },
    "fx-sydney": {
        "name": "fx-sydney",
        "title": "FX — Sydney",
        "exchange": "FX",
        "timezone": "Australia/Sydney",
        "days": "mon-fri",
        "open": "07:00",
        "close": "16:00",
        "symbols": ["AUDUSD", "NZDUSD", "AUDJPY"],
        "note": "Example: the FX day one centre at a time — copy it twice for the other two.",
    },
    "fx-london": {
        "name": "fx-london",
        "title": "FX — London",
        "exchange": "FX",
        "timezone": "Europe/London",
        "days": "mon-fri",
        "open": "08:00",
        "close": "17:00",
        "symbols": ["EURGBP", "GBPJPY", "EURCHF"],
        "note": "Example: the London centre, with the EU DST rule behind its clock.",
    },
    "fx-new-york": {
        "name": "fx-new-york",
        "title": "FX — New York",
        "exchange": "FX",
        "timezone": "America/New_York",
        "days": "mon-fri",
        "open": "08:00",
        "close": "17:00",
        "symbols": ["EURUSD", "USDJPY", "USDCAD", "USDCHF"],
        "note": "Example: the New York centre — the three together cover the FX day.",
    },
}


def library() -> list[dict[str, Any]]:
    """The built-in templates, cleaned, each flagged `builtin: True`, in picker order."""
    return [{**clean_template(BUILTINS[name], name), "builtin": True} for name in BUILTINS]


# ── settings ────────────────────────────────────────────────────────────────────────────────────

DEFAULTS: dict[str, Any] = {
    #: The template the panel shows when nothing else resolves — the all-hours market, so a first
    #: run is never "closed" for no stated reason.
    "active": "crypto-247",
    #: The user's own templates. The built-ins above are the library they copy from; a copy lands
    #: here (same name allowed, the config copy wins) and is what they edit.
    "templates": [],
    #: Symbol or root -> template name, for the symbols the library's own lists do not cover.
    "symbols": {},
    #: The roots the roll table shows, in order.
    "roots": ["ES", "NQ", "CL", "GC"],
    #: How many contract months ahead the roll table looks.
    "months": 6,
    #: How many upcoming holidays the panel lists.
    "holidays_ahead": 8,
}


def clean(patch: Any) -> dict[str, Any]:
    """An incoming settings block coerced onto DEFAULTS. Never raises; unknown keys are dropped.

    `templates` accepts a list or a {name: template} mapping (a hand-edited config is often the
    latter). A template list that arrives empty stays empty — deleting the library is the user's
    call, and the route then says so in a sentence instead of quietly re-adding templates.
    An `active` that matches no template is cleared, which reads as "show the first one".
    """
    src = patch if isinstance(patch, Mapping) else {}
    raw_templates = src.get("templates")
    templates: list[dict[str, Any]] = []
    seen: set[str] = set()
    if isinstance(raw_templates, Mapping):
        pairs: list[Any] = [(key, value) for key, value in raw_templates.items()]
    else:
        pairs = [(None, value) for value in _as_list(raw_templates)]
    for key, value in pairs:
        tpl = clean_template(value, str(key) if key else "")
        if tpl["name"] in seen:
            continue
        seen.add(tpl["name"])
        templates.append(tpl)
        if len(templates) >= 40:
            break
    names = set(BUILTINS) | {tpl["name"] for tpl in templates}

    raw_symbols = src.get("symbols")
    symbols: dict[str, str] = {}
    if isinstance(raw_symbols, Mapping):
        for key, value in raw_symbols.items():
            symbol = _text(key, 16).upper()
            target = _slug(value)
            if symbol and target in names:
                symbols[symbol] = target
            if len(symbols) >= 100:
                break

    roots: list[str] = []
    for item in _as_list(src.get("roots")):
        root = _text(item, 8).upper()
        if root in ROOTS and root not in roots:
            roots.append(root)

    active = _slug(src.get("active"))
    return {
        "active": active if active in names else "",
        "templates": templates,
        "symbols": symbols,
        "roots": roots or list(DEFAULTS["roots"]),
        "months": max(1, min(24, _int(src.get("months"), int(DEFAULTS["months"])))),
        "holidays_ahead": max(0, min(24, _int(src.get("holidays_ahead"), int(DEFAULTS["holidays_ahead"])))),
    }


def templates_of(cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The library plus the user's copies, the user's winning on a name clash.

    A copy that shadows a built-in's name STAYS a user row (`builtin: False`): the panel posts
    only its non-built-in rows back on "Copy into my templates", so flagging the user's copy as
    built-in deleted it from the config on the next copy — silently.
    """
    user = {tpl["name"]: {**tpl} for tpl in clean(cfg).get("templates", [])}
    out: list[dict[str, Any]] = []
    for tpl in library():
        mine = user.pop(tpl["name"], None)
        if mine:
            out.append({**tpl, **mine, "builtin": False})
        else:
            out.append(tpl)
    for name in sorted(user):
        out.append({**user[name], "builtin": False})
    return out


# ── the session clock ───────────────────────────────────────────────────────────────────────────

def _holiday_on(template: Mapping[str, Any], day: str) -> Optional[dict[str, Any]]:
    for entry in template.get("holidays") or []:
        if entry.get("date") == day:
            return entry
    return None


def _rule_cache(rule: str, year: int) -> dict[str, dict[str, Any]]:
    """One year of a holiday rule, memoised — the state machine asks the same question every tick."""
    key = (rule, int(year))
    if not 1900 <= key[1] <= 2200:
        return {}           # a rule table means nothing out here: the day is an ordinary day
    if key not in _RULE_CACHE:
        _RULE_CACHE[key] = {row["date"]: dict(row) for row in holiday_rule_dates(rule, [int(year)])}
    return _RULE_CACHE[key]


def holiday_on(template: Any, day: Any) -> Optional[dict[str, Any]]:
    """The holiday entry covering one date, from the template's own list or from its rule set.

    The template's own entries win, so a user can correct a rule date by writing it down. A rule is
    consulted for the date's year and the year after it, because the observed New Year's Day can fall
    on December 31 of the year before (2028's falls on 2027-12-31).
    """
    tpl = clean_template(template)
    when = parse_date(day)
    if when is None:
        return None
    explicit = _holiday_on(tpl, when.isoformat())
    if explicit:
        return explicit
    rule = str(tpl.get("holiday_rule") or "")
    if not rule:
        return None
    for year in (when.year, when.year + 1):
        found = _rule_cache(rule, year).get(when.isoformat())
        if found:
            return found
    return None


def _trades_on(template: Mapping[str, Any], day: date) -> bool:
    if (day.weekday() + 1) not in (template.get("days") or []):
        return False
    entry = holiday_on(template, day)
    return not (entry and entry.get("closed"))


def _close_minutes_on(template: Mapping[str, Any], session_start: date, wrapped: bool) -> int:
    """The close for a session that started on `session_start`, honouring an early close.

    An early close belongs to the day the session ENDS, which is the only reading that works for a
    wrap (Thanksgiving's 12:15 halt ends the session that opened the evening before).
    """
    close_day = session_start + timedelta(days=1) if wrapped else session_start
    entry = holiday_on(template, close_day)
    if entry and not entry.get("closed"):
        early = parse_minutes(entry.get("close"))
        if early is not None and early > 0:
            return early
    return close_minutes(template)


def _session_stamps(zone: str, start_day: date, start_minutes: int, close_minutes_value: int,
                    wrapped: bool) -> tuple[int, int]:
    close_day = start_day + timedelta(days=1) if wrapped else start_day
    return (_wall_to_utc_ms(zone, _wall_ms(start_day, start_minutes)),
            _wall_to_utc_ms(zone, _wall_ms(close_day, close_minutes_value)))


def next_session(template: Any, now_ms: int, horizon_days: int = 14) -> dict[str, Any]:
    """The next session whose open is still ahead, searched day by day.

    Returns {date, open_ms, close_ms} or {} when the horizon runs out. The horizon is 14 days, which
    covers every weekly pattern a template can express; a template with no trading day in it (nothing
    `clean_template` can produce, but a caller may build one by hand) answers {} rather than guessing.
    """
    tpl = clean_template(template)
    now = _clock(now_ms)
    zone = tpl["timezone"]
    local = local_parts(zone, now)
    wrapped = wraps_midnight(tpl)
    start_minutes = open_minutes(tpl)
    for step in range(0, max(1, horizon_days) + 1):
        day = local["_date"] + timedelta(days=step)
        if not _trades_on(tpl, day):
            continue
        close = _close_minutes_on(tpl, day, wrapped)
        open_ms, close_ms = _session_stamps(zone, day, start_minutes, close, wrapped)
        if open_ms > now:
            return {"date": day.isoformat(), "open_ms": open_ms, "close_ms": close_ms}
    return {}


def upcoming_holidays(template: Any, now_ms: int, count: int = 8) -> list[dict[str, Any]]:
    """The next holidays this template will be closed for (or close early for), nearest first."""
    tpl = clean_template(template)
    local = local_parts(tpl["timezone"], now_ms)
    rows: dict[str, dict[str, Any]] = {}
    rule = str(tpl.get("holiday_rule") or "")
    if rule:
        for year in (local["_date"].year - 1, local["_date"].year, local["_date"].year + 1):
            rows.update(_rule_cache(rule, year))
    for entry in tpl["holidays"]:
        rows[entry["date"]] = dict(entry)
    if count <= 0:
        return []
    today = local["_date"]
    out: list[dict[str, Any]] = []
    for key in sorted(rows):
        entry = rows[key]
        day = parse_date(key)
        if day is None or day < today:
            continue
        out.append({**entry, "days_away": (day - today).days,
                    "weekday": DAY_NAMES[day.weekday()]})
        if len(out) >= max(0, count):
            break
    return out


#: Every phase `session_state()` can report. The panel's own word table is pinned equal to this list
#: by test_sessions.py, so a phase cannot appear on the server without a word for it on screen.
PHASES = ("open", "break", "pre-open", "post-close", "holiday", "closed")


def session_state(template: Any, now_ms: Any) -> dict[str, Any]:
    """The clock for one template at one instant — open or closed, which phase, and both countdowns.

    Phases: `open`, `break` (inside the session but between a break's times), `pre-open` (a trading
    day, before its open), `post-close` (after the session that day ended), `holiday` (a holiday the
    template closes for) and `closed` (the weekend, or a day this template does not trade).
    `state` is the trading answer — "open" only while a trade can actually be placed, so a break
    reads as closed.

    `minutes_to_open` is minutes until trading next resumes (0 while it is open; the break's end
    during a break), `minutes_to_close` until the session's close. `elapsed_share` is the share of
    the session's wall-clock window already gone, and is None while no session is running — nothing
    is invented about a session that is not there.
    """
    tpl = clean_template(template)
    now = _clock(now_ms)
    zone = tpl["timezone"]
    local = local_parts(zone, now)
    start_minutes, base_close = open_minutes(tpl), close_minutes(tpl)
    span = session_span_minutes(tpl)
    wrapped = wraps_midnight(tpl)
    days = tpl["days"]
    today = local["_date"]
    yesterday = today - timedelta(days=1)

    # A session is running when its own stamps contain the instant — not when the clock is merely
    # past the open, which is how 17:00 used to read as "open" on a 09:30–16:00 session.
    open_ms = close_ms = None
    session_day = None
    for candidate in ([today] if _trades_on(tpl, today) else []) + \
                     ([yesterday] if wrapped and _trades_on(tpl, yesterday) else []):
        if span <= 0:
            break
        close_value = _close_minutes_on(tpl, candidate, wrapped)
        candidate_open, candidate_close = _session_stamps(zone, candidate, start_minutes, close_value,
                                                          wrapped)
        if candidate_open <= now < candidate_close:
            session_day, open_ms, close_ms = candidate, candidate_open, candidate_close
            span = max(1, int((close_ms - open_ms) // MINUTE_MS))
            break
    running = session_day is not None

    windows = break_windows(tpl)
    in_break = None
    for window in windows:
        if window["start_minutes"] <= local["minutes"] < window["end_minutes"]:
            in_break = window
            break

    next_open_ms = next_close_ms = None
    elapsed = None
    if running:
        phase = "break" if in_break else "open"
        next_close_ms = close_ms
        if in_break:
            reopened = _wall_to_utc_ms(zone, _wall_ms(today, in_break["end_minutes"]))
            next_open_ms = reopened if reopened > now else None
            minutes_to_open = max(0, -(-(next_open_ms - now) // MINUTE_MS)) if next_open_ms else 0
        else:
            minutes_to_open = 0
        minutes_to_close = max(0, -(-(close_ms - now) // MINUTE_MS))
        elapsed = (now - open_ms) / MINUTE_MS
        reason = "the session is in a break" if in_break else ""
        holiday = ""
    else:
        ahead = next_session(tpl, now)
        if ahead:
            next_open_ms, next_close_ms = ahead["open_ms"], ahead["close_ms"]
            minutes_to_open = max(0, -(-(ahead["open_ms"] - now) // MINUTE_MS))
            minutes_to_close = max(0, -(-(ahead["close_ms"] - now) // MINUTE_MS))
        else:
            minutes_to_open = minutes_to_close = 0
        closed_holiday = holiday_on(tpl, today) if today.weekday() + 1 in days else None
        holiday = ""
        if closed_holiday and closed_holiday.get("closed"):
            phase = "holiday"
            holiday = str(closed_holiday.get("name") or "holiday")
            reason = holiday
        elif (today.weekday() + 1) not in days:
            phase = "closed"
            reason = "the weekend" if today.weekday() >= 5 else "this template does not trade today"
        elif local["minutes"] < start_minutes:
            if wrapped and _trades_on(tpl, yesterday):
                phase = "post-close"
                reason = "after the session that opened yesterday closed"
            else:
                phase = "pre-open"
                reason = "before today's open"
        elif _trades_on(tpl, today):
            phase = "post-close"
            reason = "after the session closed"
        else:
            phase = "closed"
            reason = "no session today"

    state = "open" if phase == "open" else "closed"
    session_minutes = span if running else session_span_minutes(tpl)
    break_total = sum(window["end_minutes"] - window["start_minutes"] for window in windows)
    share = None
    if running and elapsed is not None and span > 0:
        share = round(max(0.0, min(1.0, elapsed / span)), 3)
    hours = "%s → %s %s%s" % (fmt_minutes(start_minutes), fmt_minutes(base_close), zone,
                              " (+1 day)" if wrapped else "")
    return {
        "ok": True,
        "at_ms": now,
        "template": tpl["name"],
        "title": tpl["title"],
        "exchange": tpl["exchange"],
        "timezone": zone,
        "timezone_known": zone_known(zone),
        "state": state,
        "phase": phase,
        "reason": reason,
        "holiday": holiday,
        "local": {"date": local["date"], "time": local["time"], "weekday": local["weekday"],
                  "weekday_name": local["weekday_name"], "offset_minutes": local["offset_minutes"],
                  "minutes": local["minutes"]},
        "session_date": session_day.isoformat() if running else "",
        "open_ms": open_ms,
        "close_ms": close_ms,
        "next_open_ms": next_open_ms,
        "next_close_ms": next_close_ms,
        "minutes_to_open": minutes_to_open,
        "minutes_to_close": minutes_to_close,
        "elapsed_minutes": int(elapsed) if elapsed is not None and elapsed >= 0 else None,
        "session_minutes": session_minutes,
        "break_minutes": break_total,
        "trade_minutes": max(0, session_minutes - break_total),
        "elapsed_share": share,
        "progress_pct": int(round((share or 0.0) * 100)),
        "breaks": [{"start": window["start"], "end": window["end"]} for window in windows],
        "hours": hours,
        "days": list(days),
        "problems": validate(tpl),
        "note": tpl["note"],
    }


# ── the roll calendar ───────────────────────────────────────────────────────────────────────────

#: Month codes as the industry writes them (F = January … Z = December).
MONTH_CODES = ("F", "G", "H", "J", "K", "M", "N", "Q", "U", "V", "X", "Z")
CODE_BY_MONTH = {index + 1: code for index, code in enumerate(MONTH_CODES)}

#: One rule per contract family. `months` is the delivery cycle, `expiry` the published convention,
#: and `roll_bd_before_expiry` how many business days before expiry the next month takes the volume.
FAMILIES: dict[str, dict[str, Any]] = {
    "index": {
        "label": "equity index",
        "months": (3, 6, 9, 12),
        "expiry": "the third Friday of the contract month",
        "roll_bd_before_expiry": 1,
        "venue": "CME",
        "note": "the front month settles on the third Friday's open, so its last full trading day is "
                "the Thursday before — the roll date here",
    },
    "energy": {
        "label": "energy",
        "months": tuple(range(1, 13)),
        "expiry": "three business days before the 25th of the month before delivery (the CME convention)",
        "roll_bd_before_expiry": 3,
        "venue": "NYMEX / CME",
        "note": "the front month's volume leaves before its last trading day, so the roll here is "
                "three business days early",
    },
    "metal": {
        "label": "metals",
        "months": tuple(range(1, 13)),
        "expiry": "the third-to-last business day of the contract month",
        "roll_bd_before_expiry": 1,
        "venue": "COMEX / CME",
        "note": "the last full trading day before termination",
    },
    "perpetual": {
        "label": "crypto perpetual",
        "months": (),
        "expiry": "no expiry — a perpetual has no roll",
        "roll_bd_before_expiry": 0,
        "venue": "Bybit / Binance / OKX",
        "note": "the scheduled event is funding, every eight hours at 00:00, 08:00 and 16:00 UTC",
    },
}

#: The roots the roll table knows, and what each one is.
ROOTS: dict[str, dict[str, Any]] = {
    "ES": {"family": "index", "name": "E-mini S&P 500", "venue": "CME"},
    "MES": {"family": "index", "name": "Micro E-mini S&P 500", "venue": "CME"},
    "NQ": {"family": "index", "name": "E-mini Nasdaq-100", "venue": "CME"},
    "MNQ": {"family": "index", "name": "Micro E-mini Nasdaq-100", "venue": "CME"},
    "YM": {"family": "index", "name": "E-mini Dow", "venue": "CBOT"},
    "MYM": {"family": "index", "name": "Micro E-mini Dow", "venue": "CBOT"},
    "RTY": {"family": "index", "name": "E-mini Russell 2000", "venue": "CME"},
    "M2K": {"family": "index", "name": "Micro E-mini Russell 2000", "venue": "CME"},
    "CL": {"family": "energy", "name": "WTI crude oil", "venue": "NYMEX"},
    "MCL": {"family": "energy", "name": "Micro WTI crude oil", "venue": "NYMEX"},
    "NG": {"family": "energy", "name": "Henry Hub natural gas", "venue": "NYMEX"},
    "RB": {"family": "energy", "name": "RBOB gasoline", "venue": "NYMEX"},
    "HO": {"family": "energy", "name": "NY Harbor ULSD", "venue": "NYMEX"},
    "GC": {"family": "metal", "name": "Gold", "venue": "COMEX"},
    "MGC": {"family": "metal", "name": "Micro gold", "venue": "COMEX"},
    "SI": {"family": "metal", "name": "Silver", "venue": "COMEX"},
    "SIL": {"family": "metal", "name": "Micro silver", "venue": "COMEX"},
    "HG": {"family": "metal", "name": "Copper", "venue": "COMEX"},
    "BTC": {"family": "perpetual", "name": "Bitcoin perpetual", "venue": "crypto venues"},
    "ETH": {"family": "perpetual", "name": "Ether perpetual", "venue": "crypto venues"},
    "SOL": {"family": "perpetual", "name": "Solana perpetual", "venue": "crypto venues"},
}

#: Funding boundaries of a crypto perpetual, in UTC hours.
FUNDING_HOURS: tuple[int, ...] = (0, 8, 16)


def _utc_day(ms: int) -> date:
    return _utc_dt(_clock(ms)).date()


def add_months(day: date, count: int) -> tuple[int, int]:
    """(year, month) `count` months after the given date's month."""
    total = day.year * 12 + (day.month - 1) + int(count)
    return total // 12, total % 12 + 1


def is_business_day(day: date) -> bool:
    """Monday to Friday. The roll arithmetic does not model exchange holidays — see the module docs."""
    return day.weekday() < 5


def business_days_before(day: date, count: int) -> date:
    """The date `count` business days before `day` (the day itself is not counted)."""
    cursor = day
    remaining = max(0, int(count))
    while remaining > 0:
        cursor -= timedelta(days=1)
        if is_business_day(cursor):
            remaining -= 1
    return cursor


def nth_business_day_from_end(day: date, n: int) -> date:
    """The n-th business day counting back from `day` inclusive (n=1 is `day` itself when it trades)."""
    cursor = day
    remaining = max(1, int(n))
    while True:
        if is_business_day(cursor):
            remaining -= 1
            if remaining == 0:
                return cursor
        cursor -= timedelta(days=1)


def contract_code(day: date) -> str:
    return CODE_BY_MONTH.get(day.month, "F")


def contract_label(root: str, year: int, month: int) -> str:
    """The label a desk writes: ESZ26, CLF27, GCG26."""
    return "%s%s%02d" % (root, CODE_BY_MONTH.get(month, "F"), year % 100)


def expiry_date(root: str, year: int, month: int) -> Optional[date]:
    """The last trading day of one contract, by its family's published convention."""
    family = ROOTS.get(str(root or "").upper(), {}).get("family", "")
    if family == "index":
        return _nth_weekday(year, month, 4, 3)                       # third Friday
    if family == "energy":
        reference = date(year - (month == 1), (month - 2) % 12 + 1, 25)
        if not is_business_day(reference):
            # CME Ch.200: when the 25th is not a business day the count starts from the last business
            # day before it. CLX26's 25th is a Sunday, so the three days count back from Friday the
            # 23rd — the 20th, not the 21st (§148 T4-F6).
            reference = business_days_before(reference, 1)
        return business_days_before(reference, 3)                    # three business days before that
    if family == "metal":
        cursor = date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)
        return nth_business_day_from_end(cursor, 3)                  # third-to-last business day
    return None


def parse_symbol(symbol: Any, now_ms: Any = None) -> dict[str, Any]:
    """A futures symbol split into its root, month code and year: ESZ26, ESH6, GCQ2026.

    Anything that does not carry a month code and a year is returned as a plain root (SPY, BTCUSDT)
    — the caller decides whether that is a symbol a template knows. A one- or two-digit year is
    anchored to the decade `now_ms` is standing in (ESH6 in 2026 is March 2026, not 2006); with no
    clock to anchor it a caller gets the plain 2000s reading, and the roll table only ever uses the
    ROOT anyway.
    """
    text = _text(symbol, 24).upper().replace("=F", "").replace("/", "").strip()
    found = re.match(r"^([A-Z]{1,5})([FGHJKMNQUVXZ])(\d{1,4})$", text)
    if not found:
        return {"symbol": text, "root": text, "code": "", "year": 0}
    root, code, digits = found.group(1), found.group(2), found.group(3)
    if len(digits) <= 2:
        year = 2000 + int(digits)
        if now_ms is not None:
            reference = _utc_dt(_clock(now_ms)).year
            while year < reference - 5:
                year += 10
            while year > reference + 5:
                year -= 10
    else:
        year = int(digits)
    return {"symbol": text, "root": root, "code": code, "year": year}


def root_of(symbol: Any) -> str:
    """The root a symbol belongs to: ESZ26 -> ES, ES -> ES, BTCUSDT -> BTCUSDT."""
    parsed = parse_symbol(symbol)
    if parsed["root"] and parsed["root"] in ROOTS:
        return parsed["root"]
    text = parsed["symbol"]
    if text in ROOTS:
        return text
    # A perpetual written the venue's way (BTCUSDT, ETHUSDC) names its root in front.
    for root in ROOTS:
        if ROOTS[root]["family"] == "perpetual" and text.startswith(root) and len(text) > len(root):
            return root
    return text


def _contract_row(root: str, year: int, month: int, today: date) -> Optional[dict[str, Any]]:
    expiry = expiry_date(root, year, month)
    if expiry is None:
        return None
    family = FAMILIES[ROOTS[root]["family"]]
    roll = business_days_before(expiry, int(family["roll_bd_before_expiry"]))
    return {
        "symbol": contract_label(root, year, month),
        "month": "%04d-%02d" % (year, month),
        "expiry": expiry.isoformat(),
        "roll": roll.isoformat(),
        "days_to_expiry": (expiry - today).days,
        "days_to_roll": (roll - today).days,
        "front": False,
    }


def contract_months(root: Any, now_ms: Any, count: int = 6) -> list[dict[str, Any]]:
    """The next contracts of a root that have not rolled yet, front month first."""
    key = str(root or "").upper()
    if key not in ROOTS:
        return []
    family = FAMILIES[ROOTS[key]["family"]]
    if not family["months"]:
        return []
    today = _utc_day(_clock(now_ms))
    out: list[dict[str, Any]] = []
    for step in range(0, 36):
        year, month = add_months(today, step)
        if month not in family["months"]:
            continue
        row = _contract_row(key, year, month, today)
        if row is None or row["days_to_roll"] < 0:
            continue                       # that one has already rolled
        out.append(row)
        if len(out) >= max(1, int(count)):
            break
    if out:
        out[0]["front"] = True
    return out


def funding_schedule(root: Any, now_ms: Any, count: int = 4) -> list[dict[str, Any]]:
    """The next funding stamps of a perpetual: every eight hours from 00:00 UTC."""
    key = str(root or "").upper()
    if key not in ROOTS or ROOTS[key]["family"] != "perpetual":
        return []
    moment = _clock(now_ms)
    day = _utc_day(moment)
    out: list[dict[str, Any]] = []
    for step in range(0, 4):
        current = day + timedelta(days=step)
        for hour in FUNDING_HOURS:
            stamp = _wall_ms(current, hour * 60)
            if stamp <= moment:
                continue
            out.append({"at_ms": stamp, "at": _utc_dt(stamp).strftime("%Y-%m-%d %H:%M UTC"),
                        "minutes_away": max(0, -(-(stamp - moment) // MINUTE_MS)),
                        "hours_away": round((stamp - moment) / 3_600_000, 1)})
            if len(out) >= max(1, int(count)):
                return out
    return out


def roll_calendar(root: Any, now_ms: Any, months: int = 6) -> dict[str, Any]:
    """One root's roll table: the front contract, its roll date, and the months behind it.

    A root the table does not know is refused in a sentence (never an empty table pretending to be
    one), and a perpetual answers with its funding schedule instead of contract months — because
    that is the only scheduled event a perpetual has.
    """
    key = str(root or "").upper()
    moment = _clock(now_ms)
    today = _utc_day(moment)
    if key not in ROOTS:
        return {
            "ok": False, "root": key, "kind": "unknown", "label": "", "venue": "",
            "months_rule": "", "rule": "", "note": "", "at": today.isoformat(),
            "contracts": [], "front": "", "front_month": "", "next_expiry": "", "next_roll": "",
            "days_to_roll": None, "days_to_expiry": None, "funding": [], "back_month": "",
            "detail": "no roll rule for %s — the table knows %s" % (
                key or "that", ", ".join(sorted(ROOTS))),
        }
    entry = ROOTS[key]
    family = FAMILIES[entry["family"]]
    base = {
        "ok": True, "root": key, "kind": entry["family"], "label": entry["name"],
        "venue": entry.get("venue") or family["venue"], "months_rule": ", ".join(
            MONTH_CODES[month - 1] for month in family["months"]) or "none",
        "rule": family["expiry"], "note": family["note"], "at": today.isoformat(),
    }
    if entry["family"] == "perpetual":
        funding = funding_schedule(key, moment)
        return {**base, "contracts": [], "front": "", "front_month": "", "next_expiry": "",
                "next_roll": "", "days_to_roll": None, "funding": funding,
                "hours_to_funding": funding[0]["hours_away"] if funding else None}
    contracts = contract_months(key, moment, months)
    if not contracts:
        return {**base, "ok": False, "contracts": [], "front": "", "front_month": "",
                "next_expiry": "", "next_roll": "", "days_to_roll": None, "funding": [],
                "detail": "no %s contract is ahead of today in the next three years" % key}
    front = contracts[0]
    return {**base, "contracts": contracts, "front": front["symbol"], "front_month": front["month"],
            "next_expiry": front["expiry"], "next_roll": front["roll"],
            "days_to_roll": front["days_to_roll"], "days_to_expiry": front["days_to_expiry"],
            "funding": [], "back_month": contracts[1]["symbol"] if len(contracts) > 1 else ""}


def roll_table(cfg: Any, now_ms: Any, root: str = "", months: int = 0) -> list[dict[str, Any]]:
    """The configured roots' roll tables (or the one root asked for), in the order configured."""
    settings = clean(cfg)
    wanted = str(root or "").upper()
    roots = [wanted] if wanted else list(settings["roots"])
    count = max(1, min(24, int(months) or int(settings["months"])))
    return [roll_calendar(item, now_ms, count) for item in roots]


# ── resolution ──────────────────────────────────────────────────────────────────────────────────

NO_TEMPLATE = "no session template matches %s — add one in Settings or copy a built-in"


def template_for(symbol: Any, cfg: Any) -> tuple[Optional[dict[str, Any]], str]:
    """(template, how it matched) for a symbol, or (None, "").

    The config's own `symbols` map wins, then the root (ESZ26 looks up ES), then any template whose
    `symbols` list carries the symbol or its root. Nothing else is guessed: an instrument is matched
    by a name someone wrote down, never by the shape of its ticker.
    """
    settings = clean(cfg)
    available = templates_of(settings)
    by_name = {tpl["name"]: tpl for tpl in available}
    text = _text(symbol, 24).upper()
    if not text:
        return None, ""
    mapped = settings["symbols"].get(text)
    if mapped and mapped in by_name:
        return by_name[mapped], "the symbol map in Settings"
    root = root_of(text)
    mapped = settings["symbols"].get(root)
    if mapped and mapped in by_name:
        return by_name[mapped], "the symbol map in Settings (root %s)" % root
    for tpl in available:
        symbols = tpl.get("symbols") or []
        if text in symbols:
            return tpl, "the template's own symbol list"
        if root and root in symbols:
            return tpl, "the template's own symbol list (root %s)" % root
    return None, ""


def pick_template(cfg: Any, symbol: str = "", template: str = "") -> tuple[Optional[dict[str, Any]], str]:
    """(template, how it was chosen) — by name, by symbol, else the active one, else the first."""
    settings = clean(cfg)
    if template:
        wanted = _slug(template)
        for tpl in templates_of(settings):
            if tpl["name"] == wanted:
                return tpl, "the template named in the request"
        return None, "no session template is named %s" % wanted
    if symbol:
        found, how = template_for(symbol, settings)
        if found:
            return found, how
        return None, NO_TEMPLATE % _text(symbol, 24).upper()
    available = templates_of(settings)
    if not available:
        return None, ("no session templates are configured — restore the built-ins, or copy one "
                      "from the library")
    if settings["active"]:
        for tpl in available:
            if tpl["name"] == settings["active"]:
                return tpl, "the active template in Settings"
    return available[0], "the first template (no active template is set)"


# ── the route ───────────────────────────────────────────────────────────────────────────────────

def now_ms() -> int:
    """The clock the route reads. Split out so a test can pin it."""
    return int(time.time() * 1000)


def _config() -> dict[str, Any]:
    """The stored settings block, or empty defaults when the store cannot be read."""
    try:
        from orderflow_system.desktop import config_store
        raw = (config_store.load_config() or {}).get("sessions")
    except Exception:
        raw = None
    return clean(raw)


def payload(symbol: str = "", template: str = "", root: str = "", months: int = 0,
            cfg: Any = None, at_ms: Optional[int] = None) -> dict[str, Any]:
    """The panel's whole answer, as data — the route is a thin wrapper over this.

    A refusal keeps the picker's list in the payload: the sentence tells the user to add a template
    or copy a built-in, and the list beside it is where they do it.
    """
    settings = clean(cfg) if cfg is not None else _config()
    moment = now_ms() if at_ms is None else int(at_ms)
    available = templates_of(settings)
    #: The picker's list carries the WHOLE template, so "copy into my templates" copies a template
    #: and not a summary of one (it sends this row straight back as the copy).
    listed = [{**tpl, "builtin": bool(tpl.get("builtin")),
               "active": tpl["name"] == settings["active"]} for tpl in available]
    chosen, how = pick_template(settings, symbol=symbol, template=template)
    if chosen is None:
        return {
            "ok": False, "detail": how, "at_ms": moment, "symbol": _text(symbol, 24).upper(),
            "root": "", "how": "", "template": {}, "templates": listed, "state": {},
            "rolls": [], "holidays": [],
        }
    picked_root = _text(root, 8).upper() or (root_of(symbol) if symbol else "")
    table_root = _text(root, 8).upper() or (picked_root if picked_root in ROOTS else "")
    return {
        "ok": True,
        "detail": "",
        "at_ms": moment,
        "at": _utc_dt(moment).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "symbol": _text(symbol, 24).upper(),
        "root": picked_root,
        "how": how,
        "template": chosen,
        "templates": listed,
        "state": session_state(chosen, moment),
        "holidays": upcoming_holidays(chosen, moment, settings["holidays_ahead"]),
        "rolls": roll_table(settings, moment, root=table_root, months=months),
        "settings": {"active": settings["active"], "months": settings["months"],
                     "roots": list(settings["roots"]), "symbols": dict(settings["symbols"])},
    }


@router.get("/sessions")
async def get_sessions(symbol: str = Query(default=""), template: str = Query(default=""),
                       root: str = Query(default=""), months: int = Query(default=0)) -> dict[str, Any]:
    """The session clock and the roll table — see `payload()` for the shape.

    Nothing here writes: the panel that wants to change the active template posts the settings block
    to the app's own config route.
    """
    return payload(symbol=symbol, template=template, root=root, months=months)
