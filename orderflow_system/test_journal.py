"""Journal pins: hand-computed trades for the maths, hostile text for the statement.

Every figure asserted here is worked out on paper from a fixed six-trade set (2 wins, 2 losses, a
win and a breakeven), ordered so the streaks and the drawdown curve are interesting::

    1  +10 (rr 2.0)    2  +20 (rr 3.0)    3  -5 (rr 1.0)
    4  -15 (rr 1.5)    5  +5 (rr 1.0)     6  0 (no rr)

    gross win 35, gross loss 20 → profit factor 1.75, expectancy 15/6 = 2.5
    cumulative 10, 30, 25, 10, 15, 15 → max drawdown 20
    runs  WW LL W B → longest win streak 2, longest loss streak 2

The statement tests are the safety half: a note carrying markup must come out as text, the page
must reference nothing outside itself, and an empty journal must still produce a page rather than
an exception.
"""

from __future__ import annotations

import math
import sqlite3
from typing import Any

import pytest

from orderflow_system.desktop import journal as jr

DAY0_MS = 1_700_000_000_000               # 2023-11-14T22:13:20Z — a fixed instant, never "now"
DAY_MS = 86_400_000
META = {"app": "ModFlow OrderFlow Analysis Suite", "version": "0.1.0", "account": "Sim101 (demo)"}


def _row(
    *,
    instrument: str = "ES",
    direction: str = "long",
    pnl_ticks: Any = 0.0,
    rr_ratio: Any = None,
    day: int = 0,
    notes: Any = None,
    entry_ms: int | None = None,
    exit_ms: int | None = None,
) -> dict[str, Any]:
    """A row in the ``trade_journal`` table's shape, dated ``day`` days after the fixed epoch."""
    base: dict[str, Any] = {column: None for column in jr.TRADE_COLUMNS}
    base.update(
        {
            "instrument": instrument,
            "direction": direction,
            "entry_time_ms": DAY0_MS + day * DAY_MS if entry_ms is None else entry_ms,
            "exit_time_ms": DAY0_MS + day * DAY_MS + 60_000 if exit_ms is None else exit_ms,
            "entry_price": 4500.0,
            "exit_price": 4502.0,
            "stop_loss": 4498.0,
            "take_profit": 4504.0,
            "pnl_ticks": pnl_ticks,
            "rr_ratio": rr_ratio,
            "signals_json": "[]",
            "notes": notes,
        }
    )
    return base


def _known_set() -> list[dict[str, Any]]:
    """The six trades the docstring's arithmetic is written against, in trade order."""
    return [
        _row(pnl_ticks=10.0, rr_ratio=2.0, day=0),
        _row(pnl_ticks=20.0, rr_ratio=3.0, day=0),
        _row(pnl_ticks=-5.0, rr_ratio=1.0, day=1),
        _row(pnl_ticks=-15.0, rr_ratio=1.5, day=1),
        _row(pnl_ticks=5.0, rr_ratio=1.0, day=2),
        _row(pnl_ticks=0.0, rr_ratio=None, day=2),
    ]


# ══════════════════════════════════════════════════════════════
# normalise_trades — the tolerant boundary
# ══════════════════════════════════════════════════════════════

def test_normalise_trades_coerces_shapes_and_drops_only_what_cannot_be_a_trade() -> None:
    rows: list[Any] = [
        None,                                   # nothing at all
        "garbage",                              # a string is not a row
        42,                                     # nor is a bare number
        [],                                     # nor an empty sequence
        {"instrument": "  es ", "direction": "long", "pnl_ticks": "12.5", "entry_price": "abc",
         "rr_ratio": math.nan},
        {"instrument": None, "pnl_ticks": 3.0},          # no instrument → dropped
        {"instrument": "", "pnl_ticks": 1.0},            # blank instrument → dropped
        {"instrument": "cl", "direction": "short", "pnl_ticks": True,
         "entry_time_ms": 1_700_000_000_123.9},          # bool is a category error, float stamp is not
        {"id": "7", "instrument": "nq", "pnl_ticks": None},
    ]

    out = jr.normalise_trades(rows)

    assert [trade["instrument"] for trade in out] == ["ES", "CL", "NQ"]
    es, cl, nq = out
    assert es["direction"] == "LONG"
    assert es["pnl_ticks"] == 12.5                       # a numeric string is a number
    assert es["entry_price"] is None                     # junk stays absent, not 0.0
    assert es["rr_ratio"] is None                        # NaN is absence, never propagated
    assert cl["pnl_ticks"] is None                       # True is not 1.0
    assert cl["direction"] == "SHORT"
    assert cl["entry_time_ms"] == 1_700_000_000_123
    assert nq["id"] == 7
    for trade in out:
        assert set(trade) == set(jr.TRADE_COLUMNS)       # every column always present


def test_normalise_trades_is_idempotent_and_leaves_its_input_alone() -> None:
    rows = [_row(instrument="  es ", direction="Buy", pnl_ticks="3.0")]
    before = dict(rows[0])

    once = jr.normalise_trades(rows)
    twice = jr.normalise_trades(once)

    assert rows[0] == before                             # the caller's row is untouched
    assert once == twice
    assert once[0]["direction"] == "BUY"                 # upper-cased, not re-interpreted
    assert once[0]["instrument"] == "ES"


def test_normalise_trades_reads_the_real_table_both_ways() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            "CREATE TABLE trade_journal (id INTEGER PRIMARY KEY AUTOINCREMENT, instrument TEXT NOT NULL, "
            "direction TEXT NOT NULL, entry_time_ms INTEGER, exit_time_ms INTEGER, entry_price REAL, "
            "exit_price REAL, stop_loss REAL, take_profit REAL, pnl_ticks REAL, rr_ratio REAL, "
            "signals_json TEXT, notes TEXT)"
        )
        conn.execute("INSERT INTO trade_journal (instrument, direction, pnl_ticks) VALUES ('es', 'long', 12.5)")
        conn.execute("INSERT INTO trade_journal (instrument, direction, pnl_ticks) VALUES ('nq', 'short', -3.0)")

        tuples = conn.execute("SELECT * FROM trade_journal ORDER BY id").fetchall()
        conn.row_factory = sqlite3.Row                   # what an aiosqlite caller hands us
        named = conn.execute("SELECT * FROM trade_journal ORDER BY id").fetchall()
    finally:
        conn.close()

    from_tuples = jr.normalise_trades(tuples)
    from_rows = jr.normalise_trades(named)

    assert [trade["instrument"] for trade in from_tuples] == ["ES", "NQ"]
    assert from_rows == from_tuples
    assert from_rows[0]["pnl_ticks"] == 12.5
    assert from_rows[1]["pnl_ticks"] == -3.0


def test_normalise_trades_takes_none_and_empty() -> None:
    assert jr.normalise_trades(None) == []
    assert jr.normalise_trades([]) == []


# ══════════════════════════════════════════════════════════════
# closed_trades / daily_series
# ══════════════════════════════════════════════════════════════

def test_closed_trades_keeps_the_breakeven_and_drops_the_open_position() -> None:
    rows = [*_known_set(), _row(pnl_ticks=None, day=3), None]

    closed = jr.closed_trades(rows)

    assert len(closed) == 6
    assert [trade["pnl_ticks"] for trade in closed] == [10.0, 20.0, -5.0, -15.0, 5.0, 0.0]
    assert jr.closed_trades(None) == []


def test_daily_series_buckets_by_utc_exit_day_oldest_first() -> None:
    series = jr.daily_series(_known_set())

    assert [cell["day"] for cell in series] == ["2023-11-14", "2023-11-15", "2023-11-16"]
    assert [cell["trades"] for cell in series] == [2, 2, 2]
    assert [cell["pnl"] for cell in series] == [pytest.approx(30.0), pytest.approx(-20.0), pytest.approx(5.0)]
    assert set(series[0]) == {"day", "pnl", "trades"}


def test_daily_series_uses_utc_not_local_time_off_the_midnight_edge() -> None:
    # 2023-11-14T22:13:20Z and 2023-11-15T00:31:20Z — 2 h 18 min apart, two UTC days.
    before_midnight = _row(pnl_ticks=1.0, exit_ms=DAY0_MS)
    after_midnight = _row(pnl_ticks=2.0, exit_ms=1_700_008_280_000)

    series = jr.daily_series([before_midnight, after_midnight])

    assert [cell["day"] for cell in series] == ["2023-11-14", "2023-11-15"]
    assert [cell["pnl"] for cell in series] == [pytest.approx(1.0), pytest.approx(2.0)]


def test_daily_series_falls_back_to_entry_and_skips_undated_closed_trades() -> None:
    fallen_back = _row(pnl_ticks=7.0, day=4)
    fallen_back["exit_time_ms"] = None
    undated = _row(pnl_ticks=9.0)
    undated["exit_time_ms"] = None
    undated["entry_time_ms"] = None
    still_open = _row(pnl_ticks=None, day=4)

    assert jr.daily_series([fallen_back, undated, still_open]) == [
        {"day": "2023-11-18", "pnl": 7.0, "trades": 1}
    ]
    assert jr.daily_series([]) == []


# ══════════════════════════════════════════════════════════════
# stats — the hand-computed pins
# ══════════════════════════════════════════════════════════════

def test_stats_pins_the_hand_computed_six_trade_set() -> None:
    figures = jr.stats(_known_set())

    assert figures["count"] == 6
    assert (figures["wins"], figures["losses"], figures["breakeven"]) == (3, 2, 1)
    assert figures["win_rate"] == pytest.approx(0.5)
    assert figures["gross_win"] == pytest.approx(35.0)
    assert figures["gross_loss"] == pytest.approx(20.0)
    assert figures["profit_factor"] == pytest.approx(1.75)          # 35 / 20
    assert figures["avg_win"] == pytest.approx(35.0 / 3)
    assert figures["avg_loss"] == pytest.approx(10.0)               # positive magnitude
    assert figures["expectancy"] == pytest.approx(2.5)              # 15 / 6
    assert figures["avg_rr"] == pytest.approx(1.7)                  # (2 + 3 + 1 + 1.5 + 1) / 5
    assert figures["total_pnl"] == pytest.approx(15.0)
    assert figures["best"] == pytest.approx(20.0)
    assert figures["worst"] == pytest.approx(-15.0)
    assert (figures["max_win_streak"], figures["max_loss_streak"]) == (2, 2)
    assert figures["max_drawdown"] == pytest.approx(20.0)           # peak 30 → trough 10
    # per-trade Sharpe: mean 2.5 over the sample stdev of [10, 20, -5, -15, 5, 0];
    # deviations 7.5, 17.5, -7.5, -17.5, 2.5, -2.5 → sum of squares 737.5 → var 737.5 / 5.
    assert figures["sharpe"] == pytest.approx(2.5 / math.sqrt(147.5))


def test_stats_ignores_open_positions() -> None:
    open_trade = _row(pnl_ticks=None, day=3)

    assert jr.stats([*_known_set(), open_trade])["count"] == 6
    assert jr.stats([open_trade])["count"] == 0


def test_stats_empty_is_zeroed_and_never_a_crash() -> None:
    figures = jr.stats([])

    assert figures["count"] == 0
    assert (figures["wins"], figures["losses"], figures["breakeven"]) == (0, 0, 0)
    assert figures["win_rate"] == 0.0
    assert figures["gross_win"] == 0.0
    assert figures["gross_loss"] == 0.0
    assert figures["total_pnl"] == 0.0
    assert figures["expectancy"] == 0.0
    assert figures["max_drawdown"] == 0.0
    assert (figures["max_win_streak"], figures["max_loss_streak"]) == (0, 0)
    # Nothing to average or extremise is None, not a confident 0.0.
    assert figures["profit_factor"] is None
    assert figures["avg_rr"] is None
    assert figures["sharpe"] is None
    assert figures["avg_win"] is None
    assert figures["avg_loss"] is None
    assert figures["best"] is None
    assert figures["worst"] is None
    assert jr.stats(None) == figures


def test_profit_factor_is_none_when_there_are_no_losses() -> None:
    winners = [_row(pnl_ticks=5.0, rr_ratio=1.0), _row(pnl_ticks=10.0, rr_ratio=2.0, day=1)]

    figures = jr.stats(winners)

    assert figures["profit_factor"] is None              # no fake infinity
    assert figures["gross_loss"] == 0.0
    assert figures["losses"] == 0
    assert figures["avg_loss"] is None
    assert figures["win_rate"] == pytest.approx(1.0)
    assert figures["sharpe"] is None                     # under three trades


def test_sharpe_steps_back_below_three_trades_and_on_a_flat_series() -> None:
    two = [_row(pnl_ticks=3.0), _row(pnl_ticks=-1.0, day=1)]
    assert jr.stats(two)["count"] == 2
    assert jr.stats(two)["sharpe"] is None

    identical = [_row(pnl_ticks=4.0), _row(pnl_ticks=4.0, day=1), _row(pnl_ticks=4.0, day=2)]
    assert jr.stats(identical)["count"] == 3
    assert jr.stats(identical)["sharpe"] is None         # zero spread has no Sharpe

    spread = [_row(pnl_ticks=4.0), _row(pnl_ticks=-2.0, day=1), _row(pnl_ticks=1.0, day=2)]
    assert jr.stats(spread)["sharpe"] is not None        # three trades with spread do


# ══════════════════════════════════════════════════════════════
# html_statement — the artefact
# ══════════════════════════════════════════════════════════════

def test_html_statement_carries_the_summary_figures_and_the_daily_table() -> None:
    rows = _known_set()

    out = jr.html_statement(rows, jr.stats(rows), meta=META)

    assert out.startswith("<!DOCTYPE html>")
    assert out.rstrip().endswith("</html>")
    assert META["app"] in out and META["version"] in out
    assert META["account"] in out
    assert "Generated" in out and "UTC" in out
    assert "50.0%" in out                                # win rate
    assert "1.75" in out                                 # profit factor, 2dp
    assert "1.70" in out                                 # average R multiple
    assert "2.50" in out                                 # expectancy
    for day in ("2023-11-14", "2023-11-15", "2023-11-16"):
        assert day in out                                # the daily table's three rows
    assert "-20.00" in out                               # 2023-11-15's P&L and gross loss
    assert "4,500" in out                                # prices with thousands separators
    assert "6 trades" in out and "6 closed" in out       # footer row count


def test_html_statement_is_self_contained() -> None:
    rows = _known_set()

    out = jr.html_statement(rows, jr.stats(rows), meta=META)
    lowered = out.lower()

    assert "<style>" in lowered                          # styling is inline, never fetched
    assert "<script" not in lowered
    assert "<link" not in lowered
    assert "src=" not in lowered
    assert "@import" not in lowered
    assert "http://" not in lowered and "https://" not in lowered


def test_html_statement_escapes_a_hostile_note_inert() -> None:
    hostile = "<script>alert('xss')</script>"
    rows = [_row(pnl_ticks=1.0, notes=hostile)]

    out = jr.html_statement(rows, jr.stats(rows), meta=META)

    assert "<script" not in out.lower()
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in out
    assert hostile not in out                            # the raw note never reaches the page


def test_html_statement_escapes_hostile_metadata_and_instruments() -> None:
    rows = [_row(instrument="<img src=x onerror=alert(1)>", direction="long", pnl_ticks=1.0)]
    meta = {"app": "A&B <b>Ltd</b>", "version": "1.0", "account": "<b>acct</b> & co"}

    out = jr.html_statement(rows, jr.stats(rows), meta=meta)

    assert "<img" not in out
    assert "&lt;img src=x onerror=alert(1)&gt;" in out
    assert "A&amp;B &lt;b&gt;Ltd&lt;/b&gt;" in out
    assert "&lt;b&gt;acct&lt;/b&gt; &amp; co" in out


def test_html_statement_says_n_a_where_a_ratio_cannot_exist() -> None:
    rows = [_row(pnl_ticks=5.0, rr_ratio=None)]

    out = jr.html_statement(rows, jr.stats(rows), meta=META)

    assert ">n/a<" in out                                # profit factor with no losses
    assert "100.0%" in out                               # win rate still reads as a figure


def test_html_statement_truncates_long_notes_to_sixty_characters() -> None:
    rows = [_row(pnl_ticks=1.0, notes="x" * 80)]

    out = jr.html_statement(rows, jr.stats(rows), meta=META)

    assert "x" * 60 + "…" in out
    assert "x" * 61 not in out


def test_html_statement_handles_an_empty_journal() -> None:
    out = jr.html_statement([], jr.stats([]), meta=META)

    assert out.startswith("<!DOCTYPE html>") and out.rstrip().endswith("</html>")
    assert "0 trades" in out
    assert "No trades recorded." in out
    assert "No closed trades in this period." in out
    assert ">n/a<" in out                                # every ratio of nothing is n/a


def test_html_statement_tolerates_a_missing_stats_argument_and_raw_rows() -> None:
    raw = [{"instrument": "es", "direction": "long", "pnl_ticks": "2.5", "exit_time_ms": DAY0_MS}]

    computed = jr.html_statement(raw, None, meta=META)
    bare = jr.html_statement([], None, meta=None)

    assert "2.50" in computed                            # ticks with 2dp
    assert "1 trade " in computed                        # footer count, correctly singular
    assert bare.startswith("<!DOCTYPE html>")
    assert jr.DEFAULT_APP_NAME in bare                   # the fallback header names the app
