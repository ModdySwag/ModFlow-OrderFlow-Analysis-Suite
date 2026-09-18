"""Trade-journal analytics: the numbers a trader judges a system by, and a statement worth keeping.

The engine and the bridge already record every fill in the app's own ``trade_journal`` table —
instrument, direction, entry/exit stamps and prices, stop and target, the result in ticks and the R
multiple. What was missing is the layer above it:

* **The arithmetic that decides whether a system is worth running** — win rate, expectancy, profit
  factor, average R, drawdown, streaks, a per-trade Sharpe — derived from the rows and nothing else.
* **A statement that can leave the machine** (saved, emailed, printed) in the shape every broker
  sends and none of them explains: one self-contained HTML file, inline styles only, no scripts, no
  fonts to fetch, no network — so it opens from a USB stick in ten years and cannot phone home.

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
import logging
import math
import statistics
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional

logger = logging.getLogger(__name__)

#: The product name, matching ``help.APP_NAME`` — used when ``meta`` does not name the app.
DEFAULT_APP_NAME = "ModFlow OrderFlow Analysis Suite"
#: What the statement says when ``meta`` carries no account/source note.
DEFAULT_SOURCE = "local trade journal"
#: Notes longer than this are cut in the trades table: a statement is a summary, not a minute book.
NOTE_LIMIT = 60

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
    "signals_json",
    "notes",
)

_TIME_COLUMNS = ("entry_time_ms", "exit_time_ms")
_NUMERIC_COLUMNS = ("entry_price", "exit_price", "stop_loss", "take_profit", "pnl_ticks", "rr_ratio")
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
    return dict(zip(TRADE_COLUMNS, list(row)))            # a bare tuple/CSV line, read positionally


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
        stamp = _as_int(_get(trade, "exit_time_ms"))
        if stamp is None:
            stamp = _as_int(_get(trade, "entry_time_ms"))
        pnl = _as_float(_get(trade, "pnl_ticks"))
        day = _utc_day(stamp) if stamp is not None else None
        if day is None or pnl is None:
            continue
        cell = buckets.setdefault(day, {"day": day, "pnl": 0.0, "trades": 0})
        cell["pnl"] += pnl
        cell["trades"] += 1
    return [buckets[day] for day in sorted(buckets)]


# ══════════════════════════════════════════════════════════════
# Statistics
# ══════════════════════════════════════════════════════════════

def _stats_impl(trades: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
    """The full figures dict; ``stats`` is the public name (kept separate so ``html_statement``,
    whose parameter is also called ``stats``, can still reach the implementation)."""
    pnls: list[float] = []
    rrs: list[float] = []
    for trade in closed_trades(trades):
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
        if spread > 0:
            sharpe = statistics.fmean(pnls) / spread
            if not math.isfinite(sharpe):
                sharpe = None

    return {
        "count": len(pnls),
        "wins": wins,
        "losses": losses,
        "breakeven": len(pnls) - wins - losses,
        "win_rate": wins / len(pnls) if pnls else 0.0,
        "gross_win": gross_win,
        "gross_loss": gross_loss,
        # No losses means no honest ratio: None renders as 'n/a', never as a fake infinity.
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else None,
        "avg_win": gross_win / wins if wins else None,
        "avg_loss": gross_loss / losses if losses else None,
        "expectancy": total_pnl / len(pnls) if pnls else 0.0,
        "avg_rr": statistics.fmean(rrs) if rrs else None,
        "total_pnl": total_pnl,
        "best": max(pnls) if pnls else None,
        "worst": min(pnls) if pnls else None,
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
    }


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
    """
    return _stats_impl(trades)


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
    tr.empty td { color: #8a909c; font-style: italic; }
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
    formatted for reading, a Daily table (UTC day, trades, ticks) and a Trades table (exit time
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
