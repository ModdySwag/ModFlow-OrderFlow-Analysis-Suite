"""Trade-journal analytics: the numbers a trader judges a system by, and a statement worth keeping.

The engine and the bridge already record every fill in the app's own ``trade_journal`` table —
instrument, direction, entry/exit stamps and prices, stop and target, the result in ticks and the R
multiple. What was missing is the layer above it:

* **The arithmetic that decides whether a system is worth running** — win rate, expectancy, profit
  factor, average R, drawdown, streaks, a per-trade Sharpe — derived from the rows and nothing else.
* **A statement that can leave the machine** (saved, emailed, printed) in the shape every broker
  sends and none of them explains: one self-contained HTML file, inline styles only, no scripts, no
  fonts to fetch, no network — so it opens from a USB stick in ten years and cannot phone home.
* **The layer a trader is actually graded on** — realized R per trade, expectancy and payoff in R,
  win rate per setup tag and per session, MAE/MFE when a writer records the excursions, the longest
  win and loss runs, and a Monday-first P&L calendar. The R here is *derived* from the row's own
  prices and stop wherever both exist: every writer in this repo stores the reward:risk the order
  was **opened** with, which is a plan, and averaging plans would flatter any system. Each of these
  figures degrades to ``None`` (rendered ``n/a``) when the rows do not carry the field — a made-up
  statistic is worse than an absent one, and a zero is a claim.

Two properties shape the design:

* **The rows are the user's own, so every one of them is suspect.** Columns are nullable, the
  database can be hand-edited and a bad import can leave a string where a number belongs.
  ``normalise_trades`` therefore coerces what it can, keeps ``None`` where data is absent and drops
  only what cannot be a trade at all (no instrument) — it never raises, because a statement that
  dies on one bad row is worse than one that quietly leaves it out. ``NaN``/``inf`` are treated as
  absent: a single one of them would poison every mean, streak and drawdown downstream.
* **Nothing here fakes a number.** ``profit_factor`` is ``None`` when there are no losses — an
  infinite ratio would be a lie about a sample of one kind of trade — and averages over an empty
  journal are ``None``, not ``0.0``.

Everything decision-shaped is a pure function: the same rows in, the same figures out, no database
handle, no window, no clock except the statement's own "generated" line. That is what lets the
tests pin the maths with hand-computed trades instead of a fixture the app has to be running to
produce.
"""

from __future__ import annotations

import html
import json
import logging
import math
import statistics
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping, Optional

logger = logging.getLogger(__name__)

#: The product name, matching ``help.APP_NAME`` — used when ``meta`` does not name the app.
DEFAULT_APP_NAME = "ModFlow OrderFlow Analysis Suite"
#: What the statement says when ``meta`` carries no account/source note.
DEFAULT_SOURCE = "local trade journal"
#: Notes longer than this are cut in the trades table: a statement is a summary, not a minute book.
NOTE_LIMIT = 60

#: Row keys that may name a trade's playbook tag, in the order they win. Writers disagree about the
#: column name, and a row handed to the analytics straight from a dict is not trimmed to
#: ``TRADE_COLUMNS`` — so every name one of them might have used is looked for.
SETUP_KEYS: tuple[str, ...] = ("setup", "setup_tag", "setup_name", "strategy", "playbook", "tag", "tags")
#: Row keys that may name the session a trade belongs to.
SESSION_KEYS: tuple[str, ...] = ("session", "session_name")
#: Row keys carrying the risk in ticks, for a writer that records it instead of a stop price.
RISK_KEYS: tuple[str, ...] = ("risk_ticks", "risk")
#: Row keys carrying the two excursions in ticks. Nothing in the app writes them yet; the analytics
#: read them the day a writer does, and say `n/a` until then rather than inventing a path.
MAE_KEYS: tuple[str, ...] = ("mae_ticks", "mae")
MFE_KEYS: tuple[str, ...] = ("mfe_ticks", "mfe")

#: The UTC windows a trade falls into when the row names no session of its own. The app can read
#: twenty venues and has no session table for any of them, so a real exchange calendar is not
#: guessed at; the breakdown says which rows carried a session and which were read from the clock.
SESSION_WINDOWS: tuple[tuple[str, int, int], ...] = (
    ("ASIA", 0, 7), ("LONDON", 7, 12), ("NEW YORK", 12, 21), ("OFF-HOURS", 21, 24),
)
#: Monday first — the order ``datetime.weekday()`` counts in, and the order the calendar renders.
WEEKDAY_LABELS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
#: The bucket a trade with no tag, and the one whose session cannot be read, land in.
UNTAGGED_GROUP = "UNTAGGED"
UNKNOWN_GROUP = "UNKNOWN"
#: A group needs this many trades before a sentence claims an edge in it: two is the least that can
#: disagree with a zero.
MIN_EDGE_TRADES = 2
#: The sentence set stops here. It is a summary, not a report.
MAX_SENTENCES = 5

_LONG_WORDS = frozenset({"LONG", "BUY", "BOUGHT", "BOT", "B"})
_SHORT_WORDS = frozenset({"SHORT", "SELL", "SOLD", "SLD", "S"})

#: The app's ``trade_journal`` schema in order. Sequence-shaped rows (a bare tuple from a client,
#: a CSV line) are read positionally against this list, so a plain ``fetchall()`` works too.
TRADE_COLUMNS: tuple[str, ...] = (
    "id",
    "instrument",
    "direction",
    "entry_time_ms",
    "exit_time_ms",
    "entry_price",
    "exit_price",
    "stop_loss",
    "take_profit",
    "pnl_ticks",
    "rr_ratio",
    "mae_ticks",
    "mfe_ticks",
    "signals_json",
    "notes",
)

#: The table's DDL, for writers that open the database themselves: a fresh install has no
#: ``trade_journal`` until the data layer first runs, and "End & save" must work anyway. Kept
#: beside ``TRADE_COLUMNS`` so the two cannot describe different tables; ``test_paper_ledger``
#: parses both and fails if they drift.
TRADE_JOURNAL_DDL = (
    "CREATE TABLE IF NOT EXISTS trade_journal (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    instrument TEXT NOT NULL,\n"
    "    direction TEXT NOT NULL,\n"
    "    entry_time_ms INTEGER,\n"
    "    exit_time_ms INTEGER,\n"
    "    entry_price REAL,\n"
    "    exit_price REAL,\n"
    "    stop_loss REAL,\n"
    "    take_profit REAL,\n"
    "    pnl_ticks REAL,\n"
    "    rr_ratio REAL,\n"
    "    mae_ticks REAL,\n"
    "    mfe_ticks REAL,\n"
    "    signals_json TEXT,\n"
    "    notes TEXT,\n"
    "    profile_id TEXT NOT NULL DEFAULT ''\n"
    ")"
)

#: The shortest sequence that can still be one of this table's rows: the width the journal had
#: before the excursion columns were inserted between ``rr_ratio`` and ``signals_json``. A shorter
#: sequence is a fragment, and zipping it would fabricate a trade out of whatever sat in each slot
#: (§148 T3-F10) — while a legacy row read from an older file still reads positionally.
_ROW_MIN_WIDTH = TRADE_COLUMNS.index("signals_json")

_TIME_COLUMNS = ("entry_time_ms", "exit_time_ms")
_NUMERIC_COLUMNS = ("entry_price", "exit_price", "stop_loss", "take_profit", "pnl_ticks", "rr_ratio",
                    "mae_ticks", "mfe_ticks")
#: Free-text columns copied as stripped text. ``instrument``/``direction`` are handled separately:
#: they are upper-cased, so a loop over them here would strip that back off again.
_FREETEXT_COLUMNS = ("signals_json", "notes")


# ══════════════════════════════════════════════════════════════
# Coercion — the boundary where the user's data becomes numbers
# ══════════════════════════════════════════════════════════════

def _as_float(value: Any) -> Optional[float]:
    """A finite float, or ``None``. Numeric strings are accepted; junk, ``bool``, NaN and ±inf are not.

    A numeric string is the common rot — a JSON/CSV import can write ``"12.5"`` where the schema
    says REAL, and refusing it would silently drop a real trade's P&L. ``bool`` is refused because
    ``True`` is a category error, not ``1.0``.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _as_int(value: Any) -> Optional[int]:
    """An int (epoch milliseconds), or ``None``. Floats and numeric strings round through ``float``."""
    num = _as_float(value)
    return int(num) if num is not None else None


def _as_text(value: Any) -> Optional[str]:
    """Stripped text, or ``None`` when absent or blank — an empty cell means the same as NULL here."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _get(row: Any, key: str) -> Any:
    """``row``'s value for ``key`` by mapping access when the row supports it, else ``None``.

    Tolerant on purpose: this is the read path for rows that may be dicts, ``sqlite3.Row`` objects
    or something stranger, and a missing column is absence, not an error.
    """
    try:
        return row[key]
    except Exception:  # noqa: BLE001 — an unreadable cell is an absent cell
        return None


def _row_to_mapping(row: Any) -> Optional[Mapping[str, Any]]:
    """One DB row as a name→value view, or ``None`` when it cannot be read as a row at all."""
    if isinstance(row, (str, bytes)):
        return None
    if isinstance(row, Mapping):
        return row
    keys = getattr(row, "keys", None)                     # sqlite3.Row and friends
    if callable(keys):
        return {key: row[key] for key in row.keys()}
    try:
        values = list(row)
    except TypeError:
        return None                                       # not a sequence at all
    if len(values) < _ROW_MIN_WIDTH:
        # Read positionally, a fragment fabricates a trade out of whatever sat in each slot
        # (instrument="4500.0" and the like) — it is not one of this table's rows (§148 T3-F10).
        return None
    return dict(zip(TRADE_COLUMNS, values))               # a bare tuple/CSV line, read positionally


def _utc_day(ms: int) -> Optional[str]:
    """``ms`` epoch milliseconds as a ``YYYY-MM-DD`` UTC date, or ``None`` for an impossible stamp."""
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return None


def _utc_stamp(ms: Any) -> str:
    """``ms`` as a ``YYYY-MM-DD HH:MM:SS`` UTC string; em-dash for a missing/impossible stamp."""
    stamp = _as_int(ms)
    if stamp is None:
        return "—"
    try:
        return datetime.fromtimestamp(stamp / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return "—"


# ══════════════════════════════════════════════════════════════
# Normalisation and slicing
# ══════════════════════════════════════════════════════════════

def normalise_trades(rows: Iterable[Any] | None) -> list[dict[str, Any]]:
    """Every input row as a plain trade dict; unreadable rows are dropped and nothing raises.

    ``rows`` may hold mappings (``dict``, ``sqlite3.Row``) or sequences read against
    ``TRADE_COLUMNS``, in any mix. Each output dict carries every column key — ``None`` where the
    source had nothing — with ``instrument``/``direction`` upper-cased and the numeric and time
    columns coerced. A row without an instrument cannot be a trade (an unnamed fill is
    unattributable) and is dropped, as is a row whose shape cannot be read at all; both are logged
    at debug level rather than raised. Returns ``[]`` for ``None`` or empty input.
    """
    out: list[dict[str, Any]] = []
    for row in rows or []:
        try:
            raw = _row_to_mapping(row)
        except Exception:  # noqa: BLE001 — one hostile row must not take the statement down
            logger.debug("journal: unreadable row skipped: %r", row)
            continue
        if raw is None:
            logger.debug("journal: row of unsupported type skipped: %r", type(row).__name__)
            continue
        trade: dict[str, Any] = {column: None for column in TRADE_COLUMNS}
        trade["id"] = _as_int(raw.get("id"))
        trade["instrument"] = (_as_text(raw.get("instrument")) or "").upper() or None
        trade["direction"] = (_as_text(raw.get("direction")) or "").upper() or None
        for column in _TIME_COLUMNS:
            trade[column] = _as_int(raw.get(column))
        for column in _NUMERIC_COLUMNS:
            trade[column] = _as_float(raw.get(column))
        for column in _FREETEXT_COLUMNS:
            trade[column] = _as_text(raw.get(column))
        if not trade["instrument"]:
            continue
        out.append(trade)
    return out


def closed_trades(trades: Iterable[Mapping[str, Any]] | None) -> list[Mapping[str, Any]]:
    """The rows that carry a result: ``pnl_ticks`` present. ``0.0`` (breakeven) counts, NULL does not.

    An open position has no outcome to average, so every figure below is computed from this list.
    The test is presence, not sign — a scratch trade is a real observation, and one that broke even
    is not evidence of anything else.
    """
    return [trade for trade in (trades or []) if trade is not None and _get(trade, "pnl_ticks") is not None]


def daily_series(trades: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """One row per UTC day of trading, oldest first: ``{"day": "YYYY-MM-DD", "pnl": float, "trades": int}``.

    A trade belongs to the day it exited — the day the result was booked — falling back to its
    entry day when no exit stamp was recorded. A closed trade with neither stamp is left out of the
    breakdown rather than bucketed into a made-up day, and days with no closed trades simply do not
    appear.
    """
    buckets: dict[str, dict[str, Any]] = {}
    for trade in closed_trades(trades):
        day = _result_day(trade)
        pnl = _as_float(_get(trade, "pnl_ticks"))
        if day is None or pnl is None:
            continue
        cell = buckets.setdefault(day, {"day": day, "pnl": 0.0, "trades": 0})
        cell["pnl"] += pnl
        cell["trades"] += 1
    return [{"day": cell["day"], "pnl": _finite(cell["pnl"]), "trades": cell["trades"]}
            for cell in (buckets[day] for day in sorted(buckets))]


def _result_day(trade: Any) -> Optional[str]:
    """The UTC day a trade's result is booked to: its exit day, falling back to its entry day.

    The one definition of "which day is this trade on", shared by ``daily_series`` and the calendar
    so a P&L calendar can never disagree with the daily table it is drawn from.
    """
    stamp = _as_int(_get(trade, "exit_time_ms"))
    if stamp is None:
        stamp = _as_int(_get(trade, "entry_time_ms"))
    return _utc_day(stamp) if stamp is not None else None


# ══════════════════════════════════════════════════════════════
# Statistics
# ══════════════════════════════════════════════════════════════

def _scalar_figures(rows: list[Any]) -> dict[str, Any]:
    """The flat judgement figures over already-materialised closed rows. The arithmetic home of both
    ``stats`` and the sentences, so a sentence can never quote a different win rate than the panel."""
    pnls: list[float] = []
    rrs: list[float] = []
    for trade in closed_trades(rows):
        pnl = _as_float(_get(trade, "pnl_ticks"))
        if pnl is None:
            continue                       # closed by presence, but not a usable number
        pnls.append(pnl)
        rr = _as_float(_get(trade, "rr_ratio"))
        if rr is not None:
            rrs.append(rr)

    wins = sum(1 for pnl in pnls if pnl > 0)
    losses = sum(1 for pnl in pnls if pnl < 0)
    gross_win = sum(pnl for pnl in pnls if pnl > 0)
    gross_loss = -sum(pnl for pnl in pnls if pnl < 0)      # positive magnitude
    total_pnl = sum(pnls)

    max_win_streak = 0
    max_loss_streak = 0
    win_run = 0
    loss_run = 0
    for pnl in pnls:
        if pnl > 0:
            win_run += 1
            loss_run = 0
        elif pnl < 0:
            loss_run += 1
            win_run = 0
        else:                                              # a scratch trade ends both runs
            win_run = 0
            loss_run = 0
        max_win_streak = max(max_win_streak, win_run)
        max_loss_streak = max(max_loss_streak, loss_run)

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    sharpe: Optional[float] = None
    if len(pnls) >= 3:
        spread = statistics.stdev(pnls)
        center = _mean(pnls)
        if spread > 0 and center is not None:
            sharpe = _finite(center / spread)

    return {
        "count": len(pnls),
        "wins": wins,
        "losses": losses,
        "breakeven": len(pnls) - wins - losses,
        "win_rate": wins / len(pnls) if pnls else 0.0,
        # Every derived figure below goes through _finite: a finite sum can overflow, and an
        # infinity in the payload is a 500 at the route's JSON render (§148 T3-F5).
        "gross_win": _finite(gross_win),
        "gross_loss": _finite(gross_loss),
        # No losses means no honest ratio: None renders as 'n/a', never as a fake infinity.
        "profit_factor": _finite(gross_win / gross_loss) if gross_loss > 0 else None,
        "avg_win": _finite(gross_win / wins) if wins else None,
        "avg_loss": _finite(gross_loss / losses) if losses else None,
        "expectancy": _finite(total_pnl / len(pnls)) if pnls else 0.0,
        "avg_rr": _mean(rrs),
        "total_pnl": _finite(total_pnl),
        "best": max(pnls) if pnls else None,
        "worst": min(pnls) if pnls else None,
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
        "max_drawdown": _finite(max_drawdown),
        "sharpe": sharpe,
    }


def _deep_figures(rows: list[Any], base: Mapping[str, Any]) -> dict[str, Any]:
    """The P1-7 blocks that ride along in ``stats``: R, payoff, groups, excursions, calendar.

    They sit beside the flat scalars rather than behind a second call because the journal route
    (``desktop/api.py``) hands ``stats()`` straight to the panel — a nested block is how a new
    figure reaches the UI without a second round trip or a change to the route.
    """
    r = r_summary(rows)
    avg_win = _as_float(base.get("avg_win"))
    avg_loss = _as_float(base.get("avg_loss"))
    return {
        # Average win over average loss, in ticks: the ratio a win rate has to cover to break even.
        "payoff_ratio": (avg_win / avg_loss) if (avg_win is not None and avg_loss) else None,
        "expectancy_r": r["mean"],
        "avg_win_r": r["avg_win"],
        "avg_loss_r": r["avg_loss"],
        "r_total": r["total"],
        "r_count": r["count"],
        "r_derived": r["derived"],
        "r_recorded": r["recorded"],
        "r_stops": r["stops"],
        "mae_mfe": mae_mfe(rows),
        "by_setup": by_setup(rows),
        "by_instrument": by_instrument(rows),
        "by_session": by_session(rows),
        "calendar": pnl_calendar(rows),
    }


def _stats_impl(trades: Iterable[Mapping[str, Any]] | None, *, deep: bool = True) -> dict[str, Any]:
    """The full figures dict; ``stats`` is the public name (kept separate so ``html_statement``,
    whose parameter is also called ``stats``, can still reach the implementation).

    ``deep=False`` gives the flat scalars alone — the shape ``summary_sentences`` reads when it is
    called on its own, without the round trip through the group blocks.
    """
    rows = list(trades or [])              # materialised: the deep blocks walk the rows more than once
    figures = _scalar_figures(rows)
    if not deep:
        return figures
    figures.update(_deep_figures(rows, figures))
    figures["sentences"] = summary_sentences(rows, figures=figures)
    return figures


def stats(trades: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
    """The judgement figures over the closed trades, every key always present. Pure.

    Definitions, so a number here can be argued with rather than guessed at (all P&L in ticks):

    * ``count``/``wins``/``losses``/``breakeven`` — closed trades, split by the sign of the result.
    * ``win_rate`` — ``wins / count`` in ``0..1`` (``0.0`` on an empty journal).
    * ``gross_win``/``gross_loss`` — summed wins and the **positive magnitude** of summed losses.
    * ``profit_factor`` — ``gross_win / gross_loss``; ``None`` when there are no losses, because
      the ratio would be infinity over a sample of one kind of trade.
    * ``avg_win``/``avg_loss`` — means over the winning/losing trades only (``None`` if none), with
      ``avg_loss`` a positive magnitude to match ``gross_loss``.
    * ``expectancy`` — total P&L per closed trade: the number that says whether showing up pays.
    * ``avg_rr`` — mean of ``rr_ratio`` where a value was recorded (``None`` when none was).
    * ``best``/``worst`` — largest win / largest loss (``None`` on an empty journal, not ``0.0``).
    * ``max_win_streak``/``max_loss_streak`` — longest consecutive runs in trade order; a breakeven
      trade ends both.
    * ``max_drawdown`` — peak-to-trough on the cumulative P&L curve in trade order (positive).
    * ``sharpe`` — mean divided by the sample standard deviation of the per-trade P&L series. This
      is a **per-trade** Sharpe, not an annualised one: trades are irregularly spaced, so there is
      no honest annualisation factor. ``None`` below three trades or when the spread is zero.
    * ``payoff_ratio`` — average win over average loss, both in ticks (``None`` when either is).
    * ``expectancy_r``/``avg_win_r``/``avg_loss_r``/``r_total``/``r_count`` — the same arithmetic in
      R, over the ``r_count`` closed trades that carry an R (see ``r_of`` for where an R comes
      from). ``r_derived``/``r_recorded`` say how many of those were computed from the row's own
      stop and how many are the reward:risk it was opened with — and ``r_stops`` how many closed
      rows carry a stop at all, so a sentence can tell *no stop* from *no usable one* (§148 T3-F3).
    * ``mae_mfe`` — the excursions the rows record, per result and overall (``mae_mfe``).
    * ``by_setup``/``by_instrument``/``by_session`` — the same figures grouped (`group_stats`).
    * ``calendar`` — the daily P&L as Monday-first calendar weeks (``pnl_calendar``).
    * ``sentences`` — the plain-English reading of all of it (``summary_sentences``).
    """
    return _stats_impl(trades)


# ══════════════════════════════════════════════════════════════
# P1-7 — the deep analytics: R multiples, groups, excursions, calendar
# ══════════════════════════════════════════════════════════════

def direction_sign(value: Any) -> int:
    """``+1`` for a long/buy fill, ``-1`` for a short/sell, ``0`` when the word says neither."""
    word = (_as_text(value) or "").upper()
    if word in _LONG_WORDS:
        return 1
    if word in _SHORT_WORDS:
        return -1
    return 0


def _first_present(row: Any, keys: Iterable[str]) -> Any:
    """The first of ``keys`` the row carries a value under; absence is ``None``, never an error."""
    for key in keys:
        value = _get(row, key)
        if value is not None:
            return value
    return None


def _magnitude(value: Any) -> Optional[float]:
    """How far a trade travelled, as a positive number: the sign of an excursion is not the fact."""
    num = _as_float(value)
    return abs(num) if num is not None else None


def _finite(value: Optional[float]) -> Optional[float]:
    """``value`` when it is a real number, else ``None``.

    A sum of finite rows can still overflow to an infinity (and once infinities meet, to a NaN), and
    the journal route renders with ``allow_nan=False``: one such derived figure would 500 the whole
    payload rather than read as "n/a" (§148 T3-F5).
    """
    return value if value is not None and math.isfinite(value) else None


def _mean(values: Iterable[float]) -> Optional[float]:
    """The mean of ``values``, or ``None`` when there are none — an average of nothing is not ``0.0``.

    ``fmean`` raises ``OverflowError`` when its sum overflows the float range; that is no mean to
    render, so it reads as ``None`` like any other unavailable figure (§148 T3-F5).
    """
    items = list(values)
    if not items:
        return None
    try:
        return _finite(statistics.fmean(items))
    except OverflowError:
        return None


def _tag_names(value: Any) -> list[str]:
    """Tag names out of one cell: a JSON list, a real list, a naming mapping, or plain text.

    ``signals_json`` alone is written two ways in this repo — the data layer stores
    ``[{"type": "CVD_DIVERGENCE", ...}]`` and the paper desk stores ``{"source": "paper"}`` — so a
    reader that insisted on one shape would silently drop the other writer's tags. A mapping that
    names no setup (``{"source": "paper"}``) contributes nothing rather than inventing a tag.
    """
    if value is None:
        return []
    if isinstance(value, Mapping):
        return _tag_names(_first_present(value, SETUP_KEYS) or value.get("type") or value.get("name"))
    if isinstance(value, (list, tuple, set, frozenset)):
        out: list[str] = []
        for item in value:
            out.extend(_tag_names(item))
        return out
    text = _as_text(value)
    if not text:
        return []
    if text[0] in "[{":                       # a JSON cell, the way the writers store it
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError, RecursionError):     # too deep to parse: the text stands in
            return [text]
        return _tag_names(parsed)
    return [text]


def setup_tags(trade: Any) -> list[str]:
    """The setup tags a row carries: the explicit setup columns, then what its signals cell names.

    De-duplicated case-insensitively, keeping the spelling they were read with, and read from every
    naming column the row actually carries — a row that holds both ``setup`` and ``tags`` is two
    setups, not one. A row that names nothing is untagged: no tag is invented for it, so the panel
    can say how many trades carry no setup at all instead of burying them in a bucket that reads
    like an edge.
    """
    names: list[str] = []
    seen: set[str] = set()
    sources = [*(_get(trade, key) for key in SETUP_KEYS), _get(trade, "signals_json")]
    for source in sources:
        for name in _tag_names(source):
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            names.append(name)
    return names


def _utc_hour(ms: int) -> Optional[int]:
    """``ms`` epoch milliseconds as a UTC hour ``0..23``, or ``None`` for an impossible stamp."""
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).hour
    except (OverflowError, OSError, ValueError):
        return None


def session_of(trade: Any) -> str:
    """The row's session: the name it records, else the UTC window its entry hour falls in.

    The windows are the desk's own reading of a global day (``SESSION_WINDOWS``) and are the same
    for every instrument, because the app has no session table for the twenty venues it can read. A
    row naming neither a session nor a usable stamp is ``UNKNOWN`` — the breakdown shows that bucket
    rather than dropping the trade and quietly shrinking the total.
    """
    recorded = _as_text(_first_present(trade, SESSION_KEYS))
    if recorded:
        return recorded.upper()
    stamp = _as_int(_get(trade, "entry_time_ms"))
    if stamp is None:
        stamp = _as_int(_get(trade, "exit_time_ms"))
    hour = _utc_hour(stamp) if stamp is not None else None
    if hour is None:
        return UNKNOWN_GROUP
    for label, start, end in SESSION_WINDOWS:
        if start <= hour < end:
            return label
    return UNKNOWN_GROUP


def _stop_price(trade: Any) -> Optional[float]:
    """The row's stop as a price, or ``None``: a missing stop and an exact ``0.0`` are the writers'
    "no bracket"; a negative stop is a real price (a negative-priced spread, a backwardated
    commodity) and is kept."""
    stop = _as_float(_get(trade, "stop_loss"))
    return stop if stop is not None and stop != 0.0 else None


def r_of(trade: Any) -> dict[str, Any]:
    """One trade's R multiple and where the number came from: ``{"r": float|None, "source": str|None}``.

    Three sources, best first — and the distinction is the point, because the recorded one is not a
    result:

    * ``"prices"`` — ``(exit - entry) / (entry - stop)`` in the row's own price units, oriented by
      the recorded direction and falling back to the sign of the result. This is the *realized* R:
      unit-free, because both sides of the division are prices, so no tick size is needed.
    * ``"ticks"`` — ``pnl_ticks / risk_ticks``, for a writer that records the risk directly.
    * ``"recorded"`` — the stored ``rr_ratio``, the reward:risk the order was **opened** with, so it
      is a plan rather than an outcome and is used only when nothing better exists. The only live
      writer is ``paper.Account._rr`` — ``data.models.TradeState`` never reaches ``trade_journal``
      (its ``log_trade`` has no callers). A stored ``0.0`` is the paper desk's "no bracket"
      sentinel, never a zero-R trade — and a row whose own stop sits AT its entry yields **no** R
      at all: there is no risk to divide by, and the plan is not quoted in its place (§148 T3-F2).
    """
    entry = _as_float(_get(trade, "entry_price"))
    exit_ = _as_float(_get(trade, "exit_price"))
    stop = _stop_price(trade)
    # A stop sitting AT the entry records no risk (the paper desk's break-even move). The stored
    # reward:risk is the PLAN, so a row whose own stop says "no risk" is answered with no R rather
    # than the plan's number — a plan read as an outcome is exactly what this function exists to
    # avoid (§148 T3-F2).
    risk_zero = entry is not None and stop is not None and entry == stop
    if entry is not None and exit_ is not None and stop is not None and not risk_zero:
        risk = abs(entry - stop)
        if risk > 0:
            result = _as_float(_get(trade, "pnl_ticks"))
            sign = direction_sign(_get(trade, "direction"))
            if sign == 0:
                # No direction to read: the result decides, and a scratch trade keeps the price
                # move's own sign rather than being reported as a loss it was not.
                if result is not None and result != 0:
                    sign = 1 if result > 0 else -1
                else:
                    sign = 1 if exit_ >= entry else -1
            return {"r": sign * (exit_ - entry) / risk, "source": "prices"}
    risk_ticks = _as_float(_first_present(trade, RISK_KEYS))
    result = _as_float(_get(trade, "pnl_ticks"))
    if result is not None and risk_ticks is not None and risk_ticks > 0:
        return {"r": result / risk_ticks, "source": "ticks"}
    recorded = _as_float(_get(trade, "rr_ratio"))
    if recorded is not None and recorded > 0 and not risk_zero:
        return {"r": recorded, "source": "recorded"}
    return {"r": None, "source": None}


def r_multiple(trade: Any) -> Optional[float]:
    """One trade's R multiple, or ``None`` when the row knows no risk — ``r_of`` names the sources."""
    return r_of(trade)["r"]


def r_multiples(trades: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """One entry per closed trade, in trade order: its R (``None`` where unknown) and its source.

    Aligned with ``closed_trades`` so a caller can zip the two — the per-trade R a journal table
    would show, and the input ``r_summary`` aggregates.
    """
    out: list[dict[str, Any]] = []
    for trade in closed_trades(trades):
        info = r_of(trade)
        out.append({
            "id": _as_int(_get(trade, "id")),
            "instrument": _as_text(_get(trade, "instrument")),
            "direction": _as_text(_get(trade, "direction")),
            "day": _result_day(trade),
            "pnl_ticks": _as_float(_get(trade, "pnl_ticks")),
            "r": info["r"],
            "source": info["source"],
        })
    return out


def r_summary(trades: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
    """The R side of the ledger over the closed trades: how many carry an R, where they came from,
    and the averages a trader reads an edge off.

    ``avg_win``/``avg_loss`` are positive magnitudes in R, matching ``stats()['avg_loss']`` and
    ``gross_loss``, so ``payoff_ratio`` is average win over average loss the way every other ratio
    in this module is written. ``closed`` counts the closed trades an R could have come from, and
    ``stops`` how many of them carry a stop price at all — the sentence that explains a missing R
    is worded from that count, never inferred from ``count`` (§148 T3-F3).
    """
    rows = closed_trades(trades)
    values: list[float] = []
    wins: list[float] = []
    losses: list[float] = []
    derived = 0
    recorded = 0
    stops = 0
    for trade in rows:
        if _stop_price(trade) is not None:
            stops += 1
        info = r_of(trade)
        value = _as_float(info["r"])
        if value is None:
            continue
        values.append(value)
        if info["source"] == "recorded":
            recorded += 1
        else:
            derived += 1
        if value > 0:
            wins.append(value)
        elif value < 0:
            losses.append(value)
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    avg_win = _finite(gross_win / len(wins)) if wins else None
    avg_loss = _finite(gross_loss / len(losses)) if losses else None
    return {
        "closed": len(rows),
        "count": len(values),
        "mean": _mean(values),
        "total": _finite(sum(values)) if values else None,
        "best": max(values) if values else None,
        "worst": min(values) if values else None,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff_ratio": _finite(avg_win / avg_loss) if (avg_win is not None and avg_loss) else None,
        "derived": derived,
        "recorded": recorded,
        "stops": stops,
    }


def mae_mfe(trades: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
    """The excursions the trades actually took, when the rows record one (``mae_ticks``/``mfe_ticks``).

    Both are read as magnitudes in ticks: a writer may store an adverse excursion as a negative
    number, and "how far it went against me" is the same fact either way. ``capture`` is the share
    of the favourable excursion the winning exits kept (total result over total MFE, on the winners
    that recorded one) — the number that says whether the targets are further away than the exits
    used. Every figure is ``None`` when no row records that field: nothing here is estimated.
    """
    maes: list[float] = []
    mfes: list[float] = []
    win_mae: list[float] = []
    win_mfe: list[float] = []
    loss_mae: list[float] = []
    loss_mfe: list[float] = []
    kept = 0.0
    offered = 0.0
    counted = 0
    for trade in trades or []:
        mae = _magnitude(_first_present(trade, MAE_KEYS))
        mfe = _magnitude(_first_present(trade, MFE_KEYS))
        if mae is None and mfe is None:
            continue
        counted += 1
        if mae is not None:
            maes.append(mae)
        if mfe is not None:
            mfes.append(mfe)
        result = _as_float(_get(trade, "pnl_ticks"))
        if result is not None and result > 0:
            if mae is not None:
                win_mae.append(mae)
            if mfe is not None:
                win_mfe.append(mfe)
                kept += result
                offered += mfe
        elif result is not None and result < 0:
            if mae is not None:
                loss_mae.append(mae)
            if mfe is not None:
                loss_mfe.append(mfe)
    return {
        "count": counted,
        "mae_count": len(maes),
        "mfe_count": len(mfes),
        "avg_mae": _mean(maes),
        "avg_mfe": _mean(mfes),
        "worst_mae": max(maes) if maes else None,
        "best_mfe": max(mfes) if mfes else None,
        "avg_mae_win": _mean(win_mae),
        "avg_mfe_win": _mean(win_mfe),
        "avg_mae_loss": _mean(loss_mae),
        "avg_mfe_loss": _mean(loss_mfe),
        "capture": _finite(min(1.0, kept / offered)) if offered > 0 else None,
        # Kept past offered means the booked result ran beyond the extent the row recorded, so the
        # share is clamped — it must not read as "the exits kept 150% of the run" — and this flag
        # lets the sentence say why instead (§148 T3-F6).
        "capture_over": bool(offered > 0 and kept > offered),
    }


def group_stats(
    trades: Iterable[Mapping[str, Any]] | None,
    key_of: Callable[[Any], Any],
    *,
    unknown: str = UNKNOWN_GROUP,
) -> list[dict[str, Any]]:
    """One row per group of closed trades, best average R first. Pure.

    ``key_of`` maps a trade to its group name — a string, or a list of strings when one trade
    belongs to more than one group (a trade carrying two setup tags is counted in both, so group
    counts can add up to more than the journal holds; the panel says so). Each group carries the
    same arithmetic as ``stats()``: ``pnl``/``expectancy`` in ticks, ``avg_r`` over the group's rows
    that have an R (``r_count`` of them), ``profit_factor`` ``None`` when the group never lost.

    Sorting is by average R (best first); groups with no R fall to the end, largest first, then by
    name — so the same journal always renders in the same order.
    """
    buckets: dict[str, dict[str, Any]] = {}
    order: list[str] = []                     # first-seen order keeps equal groups stable
    for trade in closed_trades(trades):
        pnl = _as_float(_get(trade, "pnl_ticks"))
        if pnl is None:
            continue
        keys = key_of(trade)
        if isinstance(keys, str):
            keys = [keys]
        for key in list(keys or []) or [unknown]:
            name = _as_text(key) or unknown
            cell = buckets.get(name)
            if cell is None:
                cell = {"key": name, "trades": 0, "wins": 0, "losses": 0, "breakeven": 0,
                        "pnl": 0.0, "gross_win": 0.0, "gross_loss": 0.0, "best": None, "worst": None,
                        "_r": []}
                buckets[name] = cell
                order.append(name)
            cell["trades"] += 1
            cell["pnl"] += pnl
            if pnl > 0:
                cell["wins"] += 1
                cell["gross_win"] += pnl
            elif pnl < 0:
                cell["losses"] += 1
                cell["gross_loss"] += -pnl
            else:
                cell["breakeven"] += 1
            cell["best"] = pnl if cell["best"] is None else max(cell["best"], pnl)
            cell["worst"] = pnl if cell["worst"] is None else min(cell["worst"], pnl)
            value = _as_float(r_of(trade)["r"])
            if value is not None:
                cell["_r"].append(value)
    out: list[dict[str, Any]] = []
    for name in order:
        cell = buckets[name]
        values = cell.pop("_r")
        cell["win_rate"] = cell["wins"] / cell["trades"] if cell["trades"] else 0.0
        cell["expectancy"] = _finite(cell["pnl"] / cell["trades"]) if cell["trades"] else 0.0
        cell["avg_r"] = _mean(values)
        cell["r_count"] = len(values)
        cell["profit_factor"] = _finite(cell["gross_win"] / cell["gross_loss"]) if cell["gross_loss"] > 0 else None
        # A finite sum of finite rows can still overflow, and an infinity anywhere in the payload is
        # a 500 at the route's JSON render (§148 T3-F5).
        cell["pnl"] = _finite(cell["pnl"])
        cell["gross_win"] = _finite(cell["gross_win"])
        cell["gross_loss"] = _finite(cell["gross_loss"])
        out.append(cell)
    out.sort(key=lambda cell: (
        0 if cell["avg_r"] is not None else 1,
        -(cell["avg_r"] or 0.0),
        -cell["trades"],
        cell["key"],
    ))
    return out


def by_setup(trades: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """``group_stats`` per setup tag; a trade that names no tag groups under ``UNTAGGED``."""
    return group_stats(trades, lambda trade: setup_tags(trade) or UNTAGGED_GROUP, unknown=UNTAGGED_GROUP)


def by_instrument(trades: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """``group_stats`` per instrument — which of them the money actually comes from."""
    return group_stats(trades, lambda trade: (_as_text(_get(trade, "instrument")) or UNKNOWN_GROUP).upper())


def by_session(trades: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """``group_stats`` per session, read from the row's own session column or its entry hour."""
    return group_stats(trades, session_of)


def _month_label(name: str) -> str:
    """``"2026-03"`` as ``"March 2026"``, or the raw key when it is not a month at all."""
    try:
        return date(int(name[:4]), int(name[5:7]), 1).strftime("%B %Y")
    except (TypeError, ValueError):
        return name


def pnl_calendar(
    trades: Iterable[Mapping[str, Any]] | None,
    *,
    month: Optional[str] = None,
) -> dict[str, Any]:
    """The daily P&L as calendar weeks — Monday first, oldest month first. Pure.

    ``{"months": [...], "total": float, "trades": int, "days": int}``, each month being
    ``{"month": "2026-03", "label": "March 2026", "weeks": [[cell|None] * 7] * N, "pnl", "trades",
    "days", "best", "worst", "peak"}``. A cell is ``daily_series``'s cell plus ``dom`` (day of the
    month) and ``weekday``; a day outside the month is ``None`` so every week row is exactly seven
    cells wide, and ``peak`` is the largest absolute daily P&L in the month — the scale a heat grid
    needs without the reader scanning the cells first. ``month`` ("YYYY-MM") keeps one month.

    Days with no closed trade stay empty rather than reading as a zero day: the calendar shows where
    the trading was, and an untouched Tuesday is not a breakeven Tuesday.
    """
    cells = {cell["day"]: dict(cell) for cell in daily_series(trades)}
    if month:
        key = str(month).strip()
        parts = key.split("-")
        if len(parts) >= 2 and len(parts[0]) == 4 and parts[0].isdigit() and parts[1].isdigit():
            prefix = f"{parts[0]}-{int(parts[1]):02d}-"     # "2023-1" and "2023-12-01" both mean a month
        else:
            # An unreadable month key is named, never answered with a silent empty calendar
            # (§148 T3-F12).
            return {"months": [], "total": 0.0, "trades": 0, "days": 0, "unknown_month": key}
        cells = {day: cell for day, cell in cells.items() if day.startswith(prefix)}
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for day in sorted(cells):
        grouped.setdefault(day[:7], {})[day] = cells[day]

    months: list[dict[str, Any]] = []
    for name in sorted(grouped):
        try:
            first = date(int(name[:4]), int(name[5:7]), 1)
        except (TypeError, ValueError):
            logger.debug("journal: calendar skipped an impossible month key: %r", name)
            continue
        nxt = date(first.year + 1, 1, 1) if first.month == 12 else date(first.year, first.month + 1, 1)
        last_day = (nxt - timedelta(days=1)).day
        offset = first.weekday()                       # Monday = 0, so a month may open mid-week
        weeks: list[list[Optional[dict[str, Any]]]] = [
            [None] * 7 for _ in range((offset + last_day + 6) // 7)
        ]
        for day_num in range(1, last_day + 1):
            stamp = date(first.year, first.month, day_num)
            key = stamp.strftime("%Y-%m-%d")
            cell = grouped[name].get(key)
            if cell is None:
                continue
            index = offset + day_num - 1
            weeks[index // 7][index % 7] = {
                "day": key, "pnl": cell["pnl"], "trades": cell["trades"],
                "dom": day_num, "weekday": stamp.weekday(),
            }
        values = [cell["pnl"] for cell in grouped[name].values()]
        months.append({
            "month": name,
            "label": _month_label(name),
            "weeks": weeks,
            "pnl": _finite(sum(values)),
            "trades": sum(cell["trades"] for cell in grouped[name].values()),
            "days": len(grouped[name]),
            "best": max(values) if values else None,
            "worst": min(values) if values else None,
            "peak": max((abs(value) for value in values), default=0.0),
        })
    return {
        "months": months,
        "total": _finite(sum(cell["pnl"] for cell in cells.values())),
        "trades": sum(cell["trades"] for cell in cells.values()),
        "days": len(cells),
    }


def _signed_text(value: Any, dp: int = 2, suffix: str = "") -> Optional[str]:
    """A number with an explicit sign — ``+2.50`` / ``-1.00`` — or ``None`` when it is absent.

    Sentences read badly without it: "expectancy 2.50 ticks" does not say which way the money goes.
    """
    num = _as_float(value)
    return f"{num:+,.{dp}f}{suffix}" if num is not None else None


def _edge_sentence(rows: list[Any]) -> Optional[str]:
    """Where the edge sits: setups first (that is where a trader can act), then sessions.

    A group is only claimed when it holds ``MIN_EDGE_TRADES`` trades, and the untagged/unknown
    buckets are never called an edge — "the edge is in the untagged setups" would be a sentence
    about the journal's data entry, not about the trading. In R when any row has an R, in ticks
    otherwise, and when nothing is positive the sentence says that instead of dressing it up.
    """
    in_r = r_summary(rows)["count"] > 0
    for groups, noun in ((by_setup(rows), "setup"), (by_session(rows), "session")):
        graded: list[tuple[float, dict[str, Any]]] = []
        for group in groups:
            if group["trades"] < MIN_EDGE_TRADES or group["key"] in (UNTAGGED_GROUP, UNKNOWN_GROUP):
                continue
            value = group["avg_r"] if in_r else group["expectancy"]
            if value is None:
                continue
            graded.append((value, group))
        if len(graded) < 2:
            continue
        graded.sort(key=lambda pair: (-pair[0], -pair[1]["trades"], pair[1]["key"]))
        best_value, best = graded[0]
        worst_value, worst = graded[-1]

        def _say(value: float) -> str:
            return _signed_text(value, 2, "R") if in_r else (_signed_text(value) + " ticks")

        def _counted(group: Mapping[str, Any]) -> str:
            """``n trades``, and how many of them carry an R when that is fewer — the R average
            rests on the rows that yield one, and a group's trade count must not imply otherwise
            (§148 T3-F14)."""
            held = f"{group['trades']} trades"
            if in_r and group.get("r_count", 0) < group["trades"]:
                held += f", {group['r_count']} with an R"
            return held

        if best_value > 0:
            text = (f"the edge is in the {best['key']} {noun}s: {_counted(best)}, "
                    f"{_say(best_value)} an average")
            if worst is not best and worst_value < 0:
                text += (f"; the weakest {noun} is {worst['key']} ({_counted(worst)}, "
                         f"{_say(worst_value)} an average)")
            return text + "."
        return (f"no {noun} group is positive — the least bad is {best['key']} "
                f"({_counted(best)}, {_say(best_value)} an average).")
    return None


def summary_sentences(
    trades: Iterable[Mapping[str, Any]] | None,
    *,
    figures: Optional[Mapping[str, Any]] = None,
) -> list[str]:
    """A compact plain-English reading of the journal: the sentences a trader would say out loud.

    ``figures`` is what ``stats()`` returned; pass ``None`` and the scalars are computed here, so
    the function stands on its own. The set is deliberately small (``MAX_SENTENCES``) and claims
    only what the rows support: an edge is named only for a group with ``MIN_EDGE_TRADES`` trades,
    and a journal whose rows record no stop is told it has no R to average rather than handed one.
    """
    rows = list(trades or [])
    if not closed_trades(rows):
        return ["no closed trades yet — nothing here can be judged until a session ends."]
    facts = dict(figures) if figures else _stats_impl(rows, deep=False)
    r = r_summary(rows)

    count = int(_as_float(facts.get("count")) or 0)
    headline = (f"{count} closed {_plural(count, 'trade', 'trades')}: "
                f"{_pct_text(facts.get('win_rate'))} win rate, expectancy "
                f"{_signed_text(facts.get('expectancy')) or 'n/a'} ticks a trade, profit factor "
                f"{_num_text(facts.get('profit_factor'))}.")

    if r["count"]:
        r_line = (f"expectancy is {_signed_text(r['mean'], 2, 'R')} over {r['count']} "
                  f"{_plural(r['count'], 'trade', 'trades')}")
        if r["avg_win"] is not None and r["avg_loss"] is not None:
            r_line += (f"; average win {_signed_text(r['avg_win'], 2, 'R')} against average loss "
                       f"{_signed_text(-abs(r['avg_loss']), 2, 'R')}")
        r_line += "."
    else:
        recorded_stops = int(_as_float(r.get("stops")) or 0)
        if recorded_stops:
            # The rows DO record a stop — they just yield no R from it (an exit is missing, say).
            # The absence of an R is not evidence that no stop was recorded (§148 T3-F3).
            r_line = (f"{recorded_stops} closed "
                      f"{_plural(recorded_stops, 'trade records', 'trades record')} a stop, but none "
                      f"yields an R from one — the figures above are in ticks.")
        else:
            r_line = "no trade records a stop, so there is no R to average — the figures above are in ticks."

    risk_bits: list[str] = []
    if int(_as_float(facts.get("losses")) or 0):
        streak = int(_as_float(facts.get("max_loss_streak")) or 0)
        risk_bits.append(f"longest losing run {streak} {_plural(streak, 'trade', 'trades')}")
    if _as_float(facts.get("max_drawdown")):
        risk_bits.append(f"deepest peak-to-trough {_num_text(facts.get('max_drawdown'))} ticks")
    risk_line = "; ".join(risk_bits) + "." if risk_bits else None

    daily = daily_series(rows)
    days_line = None
    if len(daily) >= 2:
        best_day = max(daily, key=lambda cell: cell["pnl"])
        worst_day = min(daily, key=lambda cell: cell["pnl"])
        days_line = (f"{len(daily)} trading days: the best booked {_signed_text(best_day['pnl'])} ticks "
                     f"({best_day['day']}), the worst {_signed_text(worst_day['pnl'])} ({worst_day['day']}).")

    excursions = mae_mfe(rows)
    excursion_line = None
    if excursions["count"]:
        bits: list[str] = []
        if excursions["avg_mfe_win"] is not None or excursions["avg_mae_win"] is not None:
            bits.append("winners " + " / ".join(text for text in (
                f"{_num_text(excursions['avg_mfe_win'])} ticks for" if excursions["avg_mfe_win"] is not None else None,
                f"{_num_text(excursions['avg_mae_win'])} against" if excursions["avg_mae_win"] is not None else None,
            ) if text))
        if excursions["avg_mae_loss"] is not None:
            bits.append(f"losers {_num_text(excursions['avg_mae_loss'])} ticks against")
        if excursions["capture"] is not None:
            capture_text = f"the exits kept {_pct_text(excursions['capture'])} of the run"
            if excursions.get("capture_over"):
                capture_text += " — the run as recorded is shorter than the booked result"
            bits.append(capture_text)
        if bits:
            excursion_line = "excursion: " + "; ".join(bits) + "."

    caveat = None
    if r["recorded"]:
        caveat = (f"{r['recorded']} of the {r['count']} R values came from the reward:risk the order "
                  "was opened with, not from a result.")

    candidates = [headline, r_line, caveat, _edge_sentence(rows), risk_line, days_line, excursion_line]
    return [line for line in candidates if line][:MAX_SENTENCES]


# ══════════════════════════════════════════════════════════════
# The statement — one self-contained HTML file
# ══════════════════════════════════════════════════════════════

_STYLESHEET = """
    :root { color-scheme: light dark; }
    * { box-sizing: border-box; }
    body {
      max-width: 980px; margin: 0 auto; padding: 32px 28px 48px;
      font: 13px/1.5 "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1c1f26; background: #f7f8fa;
    }
    header.head { border-bottom: 3px solid #1c1f26; padding-bottom: 12px; }
    .brand { font-size: 18px; font-weight: 700; }
    .brand .ver { font-size: 13px; font-weight: 400; color: #5c6370; }
    h1 { margin: 8px 0 4px; font-size: 15px; font-weight: 600; }
    .note { color: #5c6370; font-size: 12px; }
    section { margin-top: 22px; }
    h2 { margin: 0 0 8px; font-size: 12px; text-transform: uppercase; letter-spacing: .09em; color: #454b57; }
    table { width: 100%; border-collapse: collapse; background: #ffffff; }
    th, td { padding: 5px 8px; border: 1px solid #d7dae0; text-align: left; vertical-align: top; }
    thead th { background: #eef0f4; font-weight: 600; }
    tbody tr:nth-child(even) th, tbody tr:nth-child(even) td { background: #fafbfc; }
    .summary th[scope="row"] { width: 46%; font-weight: 500; }
    .n { text-align: right; font-variant-numeric: tabular-nums; }
    li.empty, tr.empty td { color: #8a909c; font-style: italic; }
    .says ul { margin: 0; padding-left: 18px; }
    footer { margin-top: 26px; padding-top: 10px; border-top: 1px solid #d7dae0; color: #5c6370; font-size: 12px; }
    @media print { body { background: #fff; padding: 0; } }
"""


def _escape(value: Any) -> str:
    """``str(value)`` through ``html.escape`` — the only way a value reaches the page.

    Every interpolation in ``html_statement`` goes through here, so a note, an instrument or a
    source name carrying markup is rendered as text instead of running as markup.
    """
    return html.escape(str(value))


def _num_text(value: Any, dp: int = 2, missing: str = "n/a") -> str:
    """A number with ``dp`` decimals and thousands separators (ticks convention), or ``missing``."""
    num = _as_float(value)
    return f"{num:,.{dp}f}" if num is not None else missing


def _int_text(value: Any, missing: str = "n/a") -> str:
    """A count with thousands separators, or ``missing``."""
    num = _as_float(value)
    return f"{num:,.0f}" if num is not None else missing


def _pct_text(value: Any) -> str:
    """A ``0..1`` rate as a one-decimal percentage, or ``n/a``."""
    num = _as_float(value)
    return f"{num * 100:.1f}%" if num is not None else "n/a"


def _price_text(value: Any) -> str:
    """A price with the tick size it was recorded with: up to 5 decimals, trailing zeros trimmed.

    The journal does not store the instrument's tick size, so the statement shows what the row
    holds rather than inventing decimal places — ``4500.0`` prints as ``4,500``, ``2345.25`` as
    ``2,345.25``.
    """
    num = _as_float(value)
    if num is None:
        return "—"
    return f"{num:,.5f}".rstrip("0").rstrip(".") or "0"


def _plural(count: int, singular: str, plural: str) -> str:
    """``singular`` for exactly one, ``plural`` otherwise — a statement should not read "1 trades"."""
    return singular if count == 1 else plural


def _summary_pairs(figures: Mapping[str, Any]) -> list[tuple[str, str]]:
    """The Summary table as (label, formatted value) pairs — every stat, in reading order."""
    return [
        ("Closed trades", _int_text(figures.get("count"))),
        ("Wins", _int_text(figures.get("wins"))),
        ("Losses", _int_text(figures.get("losses"))),
        ("Breakeven", _int_text(figures.get("breakeven"))),
        ("Win rate", _pct_text(figures.get("win_rate"))),
        ("Gross win (ticks)", _num_text(figures.get("gross_win"))),
        ("Gross loss (ticks)", _num_text(figures.get("gross_loss"))),
        ("Profit factor", _num_text(figures.get("profit_factor"))),
        ("Average win (ticks)", _num_text(figures.get("avg_win"))),
        ("Average loss (ticks)", _num_text(figures.get("avg_loss"))),
        ("Expectancy (ticks/trade)", _num_text(figures.get("expectancy"))),
        ("Average R multiple", _num_text(figures.get("avg_rr"))),
        ("Total P&L (ticks)", _num_text(figures.get("total_pnl"))),
        ("Best trade (ticks)", _num_text(figures.get("best"))),
        ("Worst trade (ticks)", _num_text(figures.get("worst"))),
        ("Longest win streak", _int_text(figures.get("max_win_streak"))),
        ("Longest loss streak", _int_text(figures.get("max_loss_streak"))),
        ("Max drawdown (ticks)", _num_text(figures.get("max_drawdown"))),
        ("Sharpe (per trade)", _num_text(figures.get("sharpe"))),
    ]


def _trade_row_html(trade: Mapping[str, Any]) -> str:
    """One ``<tr>`` of the Trades table; the note is truncated raw, then escaped.

    The numeric cells carry the right-align class so the columns read as a ledger, and every value
    — including the formatted numbers — passes through ``_escape``.
    """
    note = _as_text(_get(trade, "notes")) or ""
    if len(note) > NOTE_LIMIT:
        note = note[:NOTE_LIMIT] + "…"
    cells = [
        (_escape(_utc_stamp(_get(trade, "exit_time_ms"))), ""),
        (_escape(_as_text(_get(trade, "instrument")) or "—"), ""),
        (_escape(_as_text(_get(trade, "direction")) or "—"), ""),
        (_escape(_price_text(_get(trade, "entry_price"))), "n"),
        (_escape(_price_text(_get(trade, "exit_price"))), "n"),
        (_escape(_price_text(_get(trade, "stop_loss"))), "n"),
        (_escape(_price_text(_get(trade, "take_profit"))), "n"),
        (_escape(_num_text(_get(trade, "rr_ratio"), missing="—")), "n"),
        (_escape(_num_text(_get(trade, "pnl_ticks"), missing="—")), "n"),
        (_escape(note), ""),
    ]
    rendered = "".join(
        f'<td class="{css}">{text}</td>' if css else f"<td>{text}</td>" for text, css in cells
    )
    return f"        <tr>{rendered}</tr>"


def html_statement(
    trades: Iterable[Mapping[str, Any]] | None,
    stats: Optional[Mapping[str, Any]] = None,
    *,
    meta: Optional[Mapping[str, Any]] = None,
) -> str:
    """A complete, self-contained HTML statement as one string. Pure apart from the clock line.

    The shape is the one brokers send: a titled header (app name and version, the account/source
    note and the UTC moment the statement was generated), a Summary table with every statistic
    formatted for reading, a **What this says** list (``summary_sentences``), a **By setup** table
    (tag, trades, win rate, average R, tick expectancy, profit factor), a Daily table (UTC day,
    trades, ticks) and a Trades table (exit time
    UTC, instrument, direction, entry, exit, stop, target, R multiple, ticks, note truncated to
    ``NOTE_LIMIT``), then a footer count.

    ``meta`` keys, all optional: ``app``/``app_name``, ``version``, ``account`` (else ``source``,
    ``data_source``, ``note``) and ``title``. ``stats`` is what ``stats(trades)`` returned; pass
    ``None`` and it is computed from ``trades`` instead. Everything written into the page goes
    through ``html.escape`` — a note containing ``<script>`` comes out inert text — and the file
    references nothing outside itself: no script tag, no stylesheet, no font, no URL.
    """
    rows = list(trades or [])
    figures = dict(stats) if stats else _stats_impl(rows)
    info = dict(meta or {})

    app = _as_text(info.get("app")) or _as_text(info.get("app_name")) or DEFAULT_APP_NAME
    version = _as_text(info.get("version")) or ""
    source = (
        _as_text(info.get("account"))
        or _as_text(info.get("source"))
        or _as_text(info.get("data_source"))
        or _as_text(info.get("note"))
        or DEFAULT_SOURCE
    )
    title = _as_text(info.get("title")) or f"{app} — Trade Statement"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    available = sum(1 for trade in rows if _get(trade, "pnl_ticks") is not None)
    version_html = f' <span class="ver">v{_escape(version)}</span>' if version else ""

    summary_html = "\n".join(
        f'        <tr><th scope="row">{_escape(label)}</th><td class="n">{_escape(value)}</td></tr>'
        for label, value in _summary_pairs(figures)
    )

    # The P1-7 blocks, read from the figures when the caller passed a fresh ``stats()`` and computed
    # from the rows when it did not — a statement that quoted a stale stats argument would be worse
    # than one that spent a millisecond recomputing.
    sentences = list(figures.get("sentences") or summary_sentences(rows, figures=figures))
    groups = list(figures.get("by_setup") or by_setup(rows))
    says_html = "\n".join(f'        <li>{_escape(text)}</li>' for text in sentences)
    if groups:
        setups_html = "\n".join(
            "        <tr><td>{0}</td><td class=\"n\">{1}</td><td class=\"n\">{2}</td>"
            "<td class=\"n\">{3}</td><td class=\"n\">{4}</td><td class=\"n\">{5}</td></tr>".format(
                _escape(group["key"]), _escape(_int_text(group["trades"])),
                _escape(_pct_text(group["win_rate"])), _escape(_num_text(group["avg_r"], missing="—")),
                _escape(_num_text(group["expectancy"])), _escape(_num_text(group["profit_factor"])),
            )
            for group in groups
        )
    else:
        setups_html = '        <tr class="empty"><td colspan="6">No setup tags on these trades.</td></tr>'

    daily = daily_series(rows)
    if daily:
        daily_html = "\n".join(
            "        <tr><td>{0}</td><td class=\"n\">{1}</td><td class=\"n\">{2}</td></tr>".format(
                _escape(cell["day"]), _escape(_int_text(cell["trades"])), _escape(_num_text(cell["pnl"])),
            )
            for cell in daily
        )
    else:
        daily_html = '        <tr class="empty"><td colspan="3">No closed trades in this period.</td></tr>'

    if rows:
        trades_html = "\n".join(_trade_row_html(trade) for trade in rows)
    else:
        trades_html = '        <tr class="empty"><td colspan="10">No trades recorded.</td></tr>'

    footer = (
        f"{_escape(f'{len(rows):,}')} {_plural(len(rows), 'trade', 'trades')} · "
        f"{_escape(f'{available:,}')} closed · "
        f"generated by {_escape(app)}{version_html or ''}"
    )

    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{_escape(title)}</title>",
            "<style>",
            _STYLESHEET.strip("\n"),
            "</style>",
            "</head>",
            "<body>",
            '<header class="head">',
            f'  <div class="brand">{_escape(app)}{version_html}</div>',
            f"  <h1>{_escape(title)}</h1>",
            f'  <div class="note">Source: {_escape(source)} · Generated {_escape(generated)} UTC</div>',
            "</header>",
            '<section class="summary">',
            "  <h2>Summary</h2>",
            "  <table>",
            "    <tbody>",
            summary_html,
            "    </tbody>",
            "  </table>",
            "</section>",
            '<section class="says">',
            "  <h2>What this says</h2>",
            "  <ul>",
            says_html,
            "  </ul>",
            "</section>",
            '<section class="setups">',
            "  <h2>By setup</h2>",
            "  <table>",
            "    <thead>",
            '      <tr><th scope="col">Setup</th><th scope="col" class="n">Trades</th>'
            '<th scope="col" class="n">Win rate</th><th scope="col" class="n">Avg R</th>'
            '<th scope="col" class="n">Expectancy (ticks)</th><th scope="col" class="n">Profit factor</th></tr>',
            "    </thead>",
            "    <tbody>",
            setups_html,
            "    </tbody>",
            "  </table>",
            "</section>",
            '<section class="daily">',
            "  <h2>Daily</h2>",
            "  <table>",
            "    <thead>",
            '      <tr><th scope="col">Day (UTC)</th><th scope="col" class="n">Trades</th>'
            '<th scope="col" class="n">P&amp;L (ticks)</th></tr>',
            "    </thead>",
            "    <tbody>",
            daily_html,
            "    </tbody>",
            "  </table>",
            "</section>",
            '<section class="trades">',
            "  <h2>Trades</h2>",
            "  <table>",
            "    <thead>",
            "      <tr>"
            '<th scope="col">Exit (UTC)</th><th scope="col">Instrument</th><th scope="col">Dir</th>'
            '<th scope="col" class="n">Entry</th><th scope="col" class="n">Exit</th>'
            '<th scope="col" class="n">SL</th><th scope="col" class="n">TP</th>'
            '<th scope="col" class="n">R</th><th scope="col" class="n">Ticks</th>'
            '<th scope="col">Notes</th>'
            "</tr>",
            "    </thead>",
            "    <tbody>",
            trades_html,
            "    </tbody>",
            "  </table>",
            "</section>",
            f"<footer>{footer}</footer>",
            "</body>",
            "</html>",
        ]
    )
