"""P1-7 pins: the deep trade analytics — realized R, expectancy, MAE/MFE, tags, sessions, calendar.

Every figure asserted here is worked out on paper from the fixture the test names, and the fixtures
are deliberately small enough to check by eye:

* ``_r_set`` — 7 trades, 5 with a real stop/exit so the R comes from the prices (one short, one
  scratch, one row with no bracket at all) and one that only carries the stored reward:risk.
* ``_tag_set`` — the same idea per setup tag, with a two-tag row to pin the double count.
* ``_calendar_set`` — three trading days across two months, so the Monday-first grid, the empty
  days and the month totals are all visible at once.

The safety half is the degradation: a row that carries none of the optional fields must produce
``None``/``n/a`` everywhere and never a zero, because a zero is a claim about a trade. The JS half
is executed by ``desktop/ui/journal.selftest.js`` (node) and gated here, the way the sibling panel
tests gate theirs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from orderflow_system.desktop import journal as jr

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "orderflow_system" / "desktop" / "ui"
JOURNAL_JS = UI / "journal.js"
JOURNAL_SELFTEST = UI / "journal.selftest.js"

DAY0_MS = 1_700_000_000_000            # 2023-11-14T22:13:20Z, a Tuesday — the same fixed instant
DAY_MS = 86_400_000
HOUR_MS = 3_600_000
#: 2023-11-14T00:00:00Z: DAY0_MS minus its own time of day, so an hour offset is the UTC hour.
MIDNIGHT_MS = 1_699_920_020_000
#: "Not mentioned" for ``_row``'s stamp arguments, where ``None`` means "this trade has no stamp".
_ABSENT = object()


def _row(
    *,
    instrument: str = "ES",
    direction: str = "long",
    entry: Any = 4500.0,
    exit_: Any = 4504.0,
    stop: Any = 4498.0,
    pnl: Any = 16.0,
    rr: Any = 0.0,
    day: int = 0,
    entry_ms: Any = _ABSENT,
    exit_ms: Any = _ABSENT,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A trade row in the table's shape, plus whatever optional fields the test is pinning.

    ``entry_ms``/``exit_ms`` default to a stamp derived from ``day``; pass ``None`` to record a trade
    with *no* stamp at all (``_ABSENT`` is the "not mentioned" sentinel, because ``None`` is a real
    value here). Extras ride alongside the declared columns exactly as a caller handing the analytics
    its own dicts would — the SQLite read path narrows rows to ``TRADE_COLUMNS`` and therefore never
    carries them, which ``test_extras_stay_narrow_on_the_database_path`` pins.
    """
    row: dict[str, Any] = {column: None for column in jr.TRADE_COLUMNS}
    row.update(
        {
            "instrument": instrument,
            "direction": direction,
            "entry_time_ms": DAY0_MS + day * DAY_MS if entry_ms is _ABSENT else entry_ms,
            "exit_time_ms": DAY0_MS + day * DAY_MS + 60_000 if exit_ms is _ABSENT else exit_ms,
            "entry_price": entry,
            "exit_price": exit_,
            "stop_loss": stop,
            "pnl_ticks": pnl,
            "rr_ratio": rr,
            "signals_json": "[]",
        }
    )
    row.update(extras or {})
    return row


def _r_set() -> list[dict[str, Any]]:
    """The 7-trade R fixture. Paper arithmetic:

        #  dir    entry  exit    stop   risk  move   R       pnl   rr    source
        1  long    4500   4504    4498    2    +4    +2.00    +16   0.0   prices
        2  long    4500   4499    4496    4    -1    -0.25     -4   0.0   prices
        3  short  15000  14990   15010   10   -10    +1.00    +40   0.0   prices
        4  short  15000  15005   15010   10    +5    -0.50    -20   0.0   prices
        5  long    4500   4500    4498    2     0     0.00      0   0.0   prices
        6  long    4500   4502       0    —     —     none     +7   0.0   no bracket
        7  long       —      —       —    —     —    +3.00     +5   3.0   recorded

    R over #1–#5 and #7: 2 − 0.25 + 1 − 0.5 + 0 + 3 = 5.25 over 6 → mean 0.875, avg win 2.0,
    avg loss 0.375, payoff 2.0 / 0.375 = 5.33. Ticks: total 44 over 7 (gross win 68, gross loss 24),
    expectancy 44 / 7 = 6.2857, payoff 17 / 12, drawdown 20, runs (2, 1).
    """
    return [
        _row(direction="long", entry=4500.0, exit_=4504.0, stop=4498.0, pnl=16.0),
        _row(direction="long", entry=4500.0, exit_=4499.0, stop=4496.0, pnl=-4.0),
        _row(instrument="NQ", direction="short", entry=15000.0, exit_=14990.0, stop=15010.0, pnl=40.0),
        _row(instrument="NQ", direction="short", entry=15000.0, exit_=15005.0, stop=15010.0, pnl=-20.0),
        _row(direction="long", entry=4500.0, exit_=4500.0, stop=4498.0, pnl=0.0),
        _row(direction="long", entry=4500.0, exit_=4502.0, stop=0.0, pnl=7.0, rr=0.0),
        _row(direction="long", entry=None, exit_=None, stop=None, pnl=5.0, rr=3.0, day=3),
    ]


def _tag_set() -> list[dict[str, Any]]:
    """8 trades over three setups plus an untagged one, hand-computed:

        open-drive  4 trades, R +2.0 +1.5 +3.0 −0.5 → mean 1.50, ticks 20 15 30 −5 = +60
        fade        3 trades, R −1.0 −1.2 −0.8     → mean −1.00, ticks −10 −12 −8 = −30
        (untagged)  1 trade,  R +1.0               → mean 1.00,  ticks +5

    Journal: 8 closed, 4 win / 4 loss, gross win 70, gross loss 35, profit factor 2.00,
    expectancy 4.375, R mean 0.5, avg win R 1.875, avg loss R 0.875.
    """
    def trade(entry: float, exit_: float, tag: Any, pnl: float, day: int, **kw: Any) -> dict[str, Any]:
        extras = {"setup": tag} if tag is not None else {}
        return _row(entry=entry, exit_=exit_, stop=4498.0, pnl=pnl, day=day, extras=extras, **kw)

    return [
        trade(4500.0, 4504.0, "open-drive", 20.0, 0),
        trade(4500.0, 4503.0, "open-drive", 15.0, 0),
        trade(4500.0, 4506.0, "open-drive", 30.0, 1),
        trade(4500.0, 4499.0, "open-drive", -5.0, 1),
        _row(entry=4500.0, exit_=4498.0, stop=4502.0, pnl=-10.0, day=2, extras={"setup": "fade"}),
        _row(entry=4500.0, exit_=4497.6, stop=4502.0, pnl=-12.0, day=2, extras={"setup": "fade"}),
        _row(entry=4500.0, exit_=4498.4, stop=4502.0, pnl=-8.0, day=3, extras={"setup": "fade"}),
        trade(4500.0, 4502.0, None, 5.0, 4),
    ]


def _calendar_set() -> list[dict[str, Any]]:
    """Three trading days across two months: 2023-11-14 (+10), 2023-11-15 (−4), 2023-12-01 (+7)."""
    return [
        _row(pnl=10.0, exit_ms=DAY0_MS),
        _row(pnl=-4.0, exit_ms=DAY0_MS + DAY_MS),
        _row(pnl=7.0, exit_ms=DAY0_MS + 17 * DAY_MS),
    ]


# ══════════════════════════════════════════════════════════════
# direction_sign — the one word the R arithmetic needs
# ══════════════════════════════════════════════════════════════

def test_direction_sign_reads_the_words_the_writers_use() -> None:
    for word in ("long", "LONG", " buy ", "Bought", "B"):
        assert jr.direction_sign(word) == 1, word
    for word in ("short", "SELL", "sold", "s"):
        assert jr.direction_sign(word) == -1, word
    for word in (None, "", "flat", 7, True):
        assert jr.direction_sign(word) == 0, word


# ══════════════════════════════════════════════════════════════
# r_of / r_multiple / r_multiples
# ══════════════════════════════════════════════════════════════

def test_r_of_derives_the_realized_r_from_the_rows_own_prices() -> None:
    assert jr.r_of(_r_set()[0]) == {"r": 2.0, "source": "prices"}
    assert jr.r_of(_r_set()[2]) == {"r": 1.0, "source": "prices"}          # a short: the same move
    assert jr.r_of(_r_set()[3]) == {"r": -0.5, "source": "prices"}         # against the short
    assert jr.r_of(_r_set()[4]) == {"r": 0.0, "source": "prices"}          # a scratch is an R of 0
    assert jr.r_multiple(_r_set()[1]) == pytest.approx(-0.25)              # risk 4, move −1


def test_r_of_falls_back_to_the_recorded_reward_risk_only_when_it_must() -> None:
    assert jr.r_of(_r_set()[5]) == {"r": None, "source": None}             # no stop, rr 0.0 = no bracket
    assert jr.r_of(_r_set()[6]) == {"r": 3.0, "source": "recorded"}        # the stored plan, named as such


def test_r_of_prefers_the_ticks_risk_when_the_row_records_one() -> None:
    row = _row(entry=None, exit_=None, stop=None, pnl=25.0, extras={"risk_ticks": 10.0})

    assert jr.r_of(row) == {"r": 2.5, "source": "ticks"}
    assert jr.r_of(_row(entry=None, exit_=None, stop=None, pnl=25.0, extras={"risk_ticks": 0.0})) == \
        {"r": None, "source": None}                                        # a zero risk is no risk


def test_r_of_reads_a_missing_direction_off_the_result_and_never_divides_by_zero() -> None:
    blind = _row(direction=None, entry=4500.0, exit_=4506.0, stop=4498.0, pnl=12.0)
    flat = _row(direction=None, entry=4500.0, exit_=4506.0, stop=4498.0, pnl=0.0)
    square = _row(direction="long", entry=4500.0, exit_=4508.0, stop=4500.0, pnl=0.0, rr=0.0)

    assert jr.r_of(blind) == {"r": 3.0, "source": "prices"}                # +12 ticks: it was a win
    assert jr.r_of(flat) == {"r": 3.0, "source": "prices"}                 # no result: the move decides
    assert jr.r_of(square) == {"r": None, "source": None}                  # entry == stop: no risk


def test_r_of_is_tolerant_of_junk_in_every_field_it_touches() -> None:
    hostile = {"direction": "long", "entry_price": "4500.0", "exit_price": float("nan"),
               "stop_loss": "4498", "pnl_ticks": "not a number", "rr_ratio": True}
    empty = {"direction": None, "entry_price": None, "exit_price": None, "stop_loss": None}

    assert jr.r_of(hostile) == {"r": None, "source": None}
    assert jr.r_of(empty) == {"r": None, "source": None}
    assert jr.r_of(None) == {"r": None, "source": None}
    assert jr.r_multiple("not a row") is None


def test_r_multiples_aligns_with_closed_trades_in_trade_order() -> None:
    rows = [*_r_set(), _row(pnl=None, day=9)]                              # an open position at the end

    out = jr.r_multiples(rows)
    closed = jr.closed_trades(rows)

    assert len(out) == len(closed) == 7
    assert [entry["r"] for entry in out] == [2.0, -0.25, 1.0, -0.5, 0.0, None, 3.0]
    assert [entry["source"] for entry in out] == ["prices"] * 5 + [None, "recorded"]
    assert out[0]["instrument"] == "ES" and out[0]["day"] == "2023-11-14"
    assert jr.r_multiples(None) == []


# ══════════════════════════════════════════════════════════════
# r_summary and the figures it feeds into stats()
# ══════════════════════════════════════════════════════════════

def test_r_summary_pins_the_hand_computed_r_fixture() -> None:
    summary = jr.r_summary(_r_set())

    assert summary["closed"] == 7
    assert summary["count"] == 6
    assert summary["mean"] == pytest.approx(0.875)                         # 5.25 / 6
    assert summary["total"] == pytest.approx(5.25)
    assert summary["best"] == pytest.approx(3.0)
    assert summary["worst"] == pytest.approx(-0.5)
    assert summary["avg_win"] == pytest.approx(2.0)                        # (2 + 1 + 3) / 3
    assert summary["avg_loss"] == pytest.approx(0.375)                     # (0.25 + 0.5) / 2, magnitude
    assert summary["payoff_ratio"] == pytest.approx(2.0 / 0.375)
    assert (summary["derived"], summary["recorded"]) == (5, 1)             # where the numbers came from


def test_r_summary_of_nothing_is_none_and_never_zero() -> None:
    summary = jr.r_summary([])

    assert summary == {
        "closed": 0, "count": 0, "mean": None, "total": None, "best": None, "worst": None,
        "avg_win": None, "avg_loss": None, "payoff_ratio": None, "derived": 0, "recorded": 0,
        "stops": 0,
    }


def test_stats_carries_the_deep_figures_beside_the_old_ones() -> None:
    figures = jr.stats(_r_set())

    # the figures that were already there are untouched
    assert figures["count"] == 7 and figures["wins"] == 4 and figures["losses"] == 2
    assert figures["breakeven"] == 1
    assert figures["total_pnl"] == pytest.approx(44.0)
    assert figures["expectancy"] == pytest.approx(44.0 / 7)
    assert figures["gross_win"] == pytest.approx(68.0) and figures["gross_loss"] == pytest.approx(24.0)
    assert figures["profit_factor"] == pytest.approx(68.0 / 24.0)
    assert (figures["max_win_streak"], figures["max_loss_streak"]) == (2, 1)
    assert figures["max_drawdown"] == pytest.approx(20.0)

    # and the deep ones ride beside them
    assert figures["payoff_ratio"] == pytest.approx(17.0 / 12.0)
    assert figures["expectancy_r"] == pytest.approx(0.875)
    assert figures["avg_win_r"] == pytest.approx(2.0)
    assert figures["avg_loss_r"] == pytest.approx(0.375)
    assert figures["r_total"] == pytest.approx(5.25)
    assert (figures["r_count"], figures["r_derived"], figures["r_recorded"]) == (6, 5, 1)
    assert set(figures) >= {"mae_mfe", "by_setup", "by_instrument", "by_session", "calendar", "sentences"}


def test_stats_is_deterministic_and_its_empty_shape_is_stable() -> None:
    assert jr.stats(None) == jr.stats([])
    empty = jr.stats([])

    assert empty["expectancy_r"] is None and empty["payoff_ratio"] is None
    assert empty["r_total"] is None and empty["r_count"] == 0
    assert empty["by_setup"] == [] and empty["by_instrument"] == [] and empty["by_session"] == []
    assert empty["calendar"] == {"months": [], "total": 0.0, "trades": 0, "days": 0}
    assert empty["mae_mfe"]["count"] == 0 and empty["mae_mfe"]["avg_mae"] is None
    assert empty["sentences"] == ["no closed trades yet — nothing here can be judged until a session ends."]


def test_stats_tolerates_a_hostile_journal_whole() -> None:
    rows: list[Any] = [None, "garbage", 42, [], _row(pnl="12.5"), {"instrument": "", "pnl_ticks": 1.0}]

    figures = jr.stats(rows)

    # A numeric string is still a number, and nothing raised on the rows that are not rows at all.
    assert figures["count"] == 2 and figures["total_pnl"] == pytest.approx(13.5)
    assert figures["by_setup"][0]["key"] == jr.UNTAGGED_GROUP           # an untagged row still counts

    # Dropping the row that cannot be a trade is the boundary's job, not the analytics'.
    assert jr.stats(jr.normalise_trades(rows))["count"] == 1


# ══════════════════════════════════════════════════════════════
# mae_mfe
# ══════════════════════════════════════════════════════════════

def test_mae_mfe_pins_the_excursions_and_where_the_winners_stopped() -> None:
    # winners: +10 with mae 3 / mfe 20, +6 with mae −2 (a writer's sign) / mfe 9 → 16 kept of 29 run
    # loser:   −5 with mae 12 / mfe 4; the open row counts in the overall averages only
    rows = [
        _row(pnl=10.0, extras={"mae_ticks": 3.0, "mfe_ticks": 20.0}),
        _row(pnl=6.0, extras={"mae_ticks": -2.0, "mfe_ticks": 9.0}),
        _row(pnl=-5.0, extras={"mae_ticks": 12.0, "mfe_ticks": 4.0}, day=1),
        _row(pnl=None, extras={"mae": 1.0, "mfe": 2.0}, day=2),
    ]

    out = jr.mae_mfe(rows)

    assert out["count"] == 4 and out["mae_count"] == 4 and out["mfe_count"] == 4
    assert out["avg_mae"] == pytest.approx(4.5)                          # (3 + 2 + 12 + 1) / 4
    assert out["avg_mfe"] == pytest.approx(8.75)                         # (20 + 9 + 4 + 2) / 4
    assert out["avg_mae_win"] == pytest.approx(2.5)
    assert out["avg_mfe_win"] == pytest.approx(14.5)
    assert out["avg_mae_loss"] == pytest.approx(12.0) and out["avg_mfe_loss"] == pytest.approx(4.0)
    assert out["worst_mae"] == pytest.approx(12.0) and out["best_mfe"] == pytest.approx(20.0)
    assert out["capture"] == pytest.approx(16.0 / 29.0)


def test_mae_mfe_without_the_fields_is_all_none() -> None:
    out = jr.mae_mfe(_r_set())

    assert out["count"] == 0 and out["mae_count"] == 0 and out["mfe_count"] == 0
    assert out["avg_mae"] is None and out["avg_mfe"] is None and out["capture"] is None
    assert out["worst_mae"] is None and out["best_mfe"] is None
    assert out["avg_mae_win"] is None and out["avg_mae_loss"] is None


def test_mae_mfe_ignores_a_capture_it_cannot_divide() -> None:
    only_losers = [_row(pnl=-5.0, extras={"mfe_ticks": 0.0, "mae_ticks": 6.0})]

    assert jr.mae_mfe(only_losers)["capture"] is None                    # no run to have kept


# ══════════════════════════════════════════════════════════════
# setup tags
# ══════════════════════════════════════════════════════════════

def test_setup_tags_read_every_shape_the_writers_leave_behind() -> None:
    explicit = _row(extras={"setup": "open-drive"})
    signals = _row(extras={"signals_json": json.dumps([{"type": "CVD_DIVERGENCE", "strength": 3},
                                                       {"type": "ABSORPTION"}])})
    strings = _row(extras={"tags": ["Open-Drive", "OPEN-DRIVE", " fade "]})
    plain = _row(extras={"signals_json": "open-drive"})
    hostile = _row(extras={"signals_json": "{not json at all"})
    source_only = _row(extras={"signals_json": '{"source": "paper"}'})
    named = _row(extras={"signals_json": json.dumps({"setup": "opening range"})})

    assert jr.setup_tags(explicit) == ["open-drive"]
    assert jr.setup_tags(signals) == ["CVD_DIVERGENCE", "ABSORPTION"]
    assert jr.setup_tags(strings) == ["Open-Drive", "fade"]              # de-duped, spelled as read
    assert jr.setup_tags(plain) == ["open-drive"]
    assert jr.setup_tags(hostile) == ["{not json at all"]                # text is a name, not a crash
    assert jr.setup_tags(source_only) == []                              # "paper" is not a setup
    assert jr.setup_tags(named) == ["opening range"]
    assert jr.setup_tags(_row()) == []


def test_setup_tags_reads_a_real_column_before_the_signals_cell() -> None:
    row = _row(extras={"setup": "open-drive", "signals_json": '["fade"]'})

    assert jr.setup_tags(row) == ["open-drive", "fade"]


# ══════════════════════════════════════════════════════════════
# group_stats / by_setup / by_instrument / by_session
# ══════════════════════════════════════════════════════════════

def test_by_setup_pins_the_hand_computed_tag_groups() -> None:
    groups = {group["key"]: group for group in jr.by_setup(_tag_set())}

    assert set(groups) == {"open-drive", "fade", jr.UNTAGGED_GROUP}
    drive = groups["open-drive"]
    assert (drive["trades"], drive["wins"], drive["losses"]) == (4, 3, 1)
    assert drive["win_rate"] == pytest.approx(0.75)
    assert drive["pnl"] == pytest.approx(60.0)
    assert drive["expectancy"] == pytest.approx(15.0)
    assert drive["avg_r"] == pytest.approx(1.5) and drive["r_count"] == 4
    assert drive["profit_factor"] == pytest.approx(65.0 / 5.0)
    assert (drive["best"], drive["worst"]) == (30.0, -5.0)

    fade = groups["fade"]
    assert (fade["trades"], fade["wins"], fade["losses"]) == (3, 0, 3)
    assert fade["win_rate"] == pytest.approx(0.0)
    assert fade["pnl"] == pytest.approx(-30.0)
    assert fade["avg_r"] == pytest.approx(-1.0)
    assert fade["profit_factor"] == pytest.approx(0.0)                   # nothing won: a real zero
    assert groups[jr.UNTAGGED_GROUP]["avg_r"] == pytest.approx(1.0)


def test_by_setup_sorts_by_average_r_best_first_with_no_r_groups_last() -> None:
    rows = [
        *_tag_set(),
        # tagged, but nobody recorded a stop or an exit, so the group has no R to average
        _row(entry=None, exit_=None, stop=0.0, pnl=1.0, day=5, extras={"setup": "no-stop-play"}),
    ]

    keys = [group["key"] for group in jr.by_setup(rows)]

    assert keys == ["open-drive", jr.UNTAGGED_GROUP, "fade", "no-stop-play"]
    assert jr.by_setup(rows)[-1]["avg_r"] is None


def test_a_trade_with_two_tags_is_counted_in_both() -> None:
    row = _row(entry=4500.0, exit_=4504.0, stop=4498.0, pnl=20.0, extras={"setup": "open-drive",
                                                                          "tags": ["fade"]})

    groups = {group["key"]: group for group in jr.by_setup([row])}

    assert groups["open-drive"]["trades"] == 1 and groups["fade"]["trades"] == 1
    assert sum(group["trades"] for group in groups.values()) == 2          # the double count is real


def test_group_stats_of_nothing_is_an_empty_list_and_keeps_the_unknown_bucket() -> None:
    assert jr.by_setup([]) == [] and jr.by_instrument([]) == [] and jr.by_session([]) == []
    assert jr.by_instrument(None) == []

    loose = jr.by_instrument([{"pnl_ticks": 3.0}])
    assert [group["key"] for group in loose] == [jr.UNKNOWN_GROUP]


def test_by_instrument_groups_the_same_maths_per_symbol() -> None:
    rows = [_row(instrument="ES", pnl=10.0), _row(instrument=" es ", pnl=-4.0, day=1),
            _row(instrument="cl", pnl=2.0, day=2)]

    groups = {group["key"]: group for group in jr.by_instrument(jr.normalise_trades(rows))}

    assert set(groups) == {"ES", "CL"}
    assert groups["ES"]["trades"] == 2 and groups["ES"]["pnl"] == pytest.approx(6.0)
    assert groups["ES"]["win_rate"] == pytest.approx(0.5)
    assert groups["CL"]["trades"] == 1


def test_group_stats_only_counts_closed_trades() -> None:
    rows = [*_tag_set(), _row(pnl=None, day=9, extras={"setup": "open-drive"})]

    groups = {group["key"]: group for group in jr.by_setup(rows)}

    assert groups["open-drive"]["trades"] == 4                             # the open row is not a result


# ══════════════════════════════════════════════════════════════
# sessions
# ══════════════════════════════════════════════════════════════

def test_session_of_pins_the_utc_window_boundaries() -> None:
    cases = {
        0: "ASIA", 6: "ASIA", 7: "LONDON", 11: "LONDON", 12: "NEW YORK",
        20: "NEW YORK", 21: "OFF-HOURS", 23: "OFF-HOURS",
    }

    for hour, expected in cases.items():
        stamp = MIDNIGHT_MS + hour * HOUR_MS
        assert jr.session_of(_row(entry_ms=stamp, exit_ms=stamp)) == expected, hour


def test_session_of_prefers_a_recorded_session_and_falls_back_clearly() -> None:
    assert jr.session_of(_row(extras={"session": "rth"})) == "RTH"        # the row's own word wins
    assert jr.session_of(_row(extras={"session_name": " london "})) == "LONDON"
    assert jr.session_of(_row(entry_ms=None, exit_ms=None)) == jr.UNKNOWN_GROUP
    assert jr.session_of({"pnl_ticks": 1.0}) == jr.UNKNOWN_GROUP
    only_exit = _row(entry_ms=None, exit_ms=MIDNIGHT_MS + 8 * HOUR_MS)
    assert jr.session_of(only_exit) == "LONDON"                            # the exit stamps the window


def test_by_session_groups_the_clock_and_keeps_the_unknown_bucket() -> None:
    rows = [
        _row(pnl=10.0, entry_ms=MIDNIGHT_MS + 3 * HOUR_MS, exit_ms=MIDNIGHT_MS + 3 * HOUR_MS),
        _row(pnl=-5.0, entry_ms=MIDNIGHT_MS + 10 * HOUR_MS, exit_ms=MIDNIGHT_MS + 10 * HOUR_MS),
        _row(pnl=4.0, entry_ms=MIDNIGHT_MS + 15 * HOUR_MS, exit_ms=MIDNIGHT_MS + 15 * HOUR_MS),
        _row(pnl=-1.0, entry_ms=MIDNIGHT_MS + 23 * HOUR_MS, exit_ms=MIDNIGHT_MS + 23 * HOUR_MS),
        _row(pnl=2.0, entry_ms=None, exit_ms=None),
    ]

    groups = {group["key"]: group["trades"] for group in jr.by_session(rows)}

    assert groups == {"ASIA": 1, "LONDON": 1, "NEW YORK": 1, "OFF-HOURS": 1, jr.UNKNOWN_GROUP: 1}


# ══════════════════════════════════════════════════════════════
# the P&L calendar
# ══════════════════════════════════════════════════════════════

def test_pnl_calendar_lays_the_days_out_monday_first() -> None:
    calendar = jr.pnl_calendar(_calendar_set())
    months = {month["month"]: month for month in calendar["months"]}

    assert set(months) == {"2023-11", "2023-12"}
    assert calendar["total"] == pytest.approx(13.0)
    assert calendar["trades"] == 3 and calendar["days"] == 3

    november = months["2023-11"]
    # 1 Nov 2023 is a Wednesday, so the first week opens with two cells of October.
    assert len(november["weeks"]) == 5
    assert november["weeks"][0][0] is None and november["weeks"][0][1] is None
    assert november["weeks"][0][2] is None                                  # Wednesday: no trade that day
    assert november["weeks"][2][1]["day"] == "2023-11-14"                   # the Tuesday of that week
    assert november["weeks"][2][1]["weekday"] == 1 and november["weeks"][2][1]["dom"] == 14
    assert november["weeks"][2][2]["day"] == "2023-11-15"
    assert november["weeks"][2][0] is None                                  # the Monday had no trade
    assert (november["pnl"], november["trades"], november["days"]) == (6.0, 2, 2)
    assert (november["best"], november["worst"], november["peak"]) == (10.0, -4.0, 10.0)
    assert november["label"] == "November 2023"

    december = months["2023-12"]
    assert len(december["weeks"]) == 5
    assert december["weeks"][0][4]["day"] == "2023-12-01"                   # 1 Dec 2023 is a Friday
    assert december["peak"] == pytest.approx(7.0)


def test_pnl_calendar_weeks_are_always_seven_cells_and_never_a_zero_day() -> None:
    calendar = jr.pnl_calendar(_calendar_set())

    for month in calendar["months"]:
        assert all(len(week) == 7 for week in month["weeks"])
        assert (len(month["weeks"]) * 7) >= month["days"]


def test_pnl_calendar_can_keep_one_month_and_totals_only_what_it_keeps() -> None:
    calendar = jr.pnl_calendar(_calendar_set(), month="2023-12")

    assert [month["month"] for month in calendar["months"]] == ["2023-12"]
    assert calendar["total"] == pytest.approx(7.0) and calendar["days"] == 1


def test_pnl_calendar_agrees_with_the_daily_series_it_is_drawn_from() -> None:
    served = {cell["day"]: cell["pnl"] for cell in jr.daily_series(_calendar_set())}
    drawn = {}
    for month in jr.pnl_calendar(_calendar_set())["months"]:
        for week in month["weeks"]:
            for cell in week:
                if cell:
                    drawn[cell["day"]] = cell["pnl"]

    assert drawn == served


def test_pnl_calendar_of_an_empty_or_undated_journal_is_empty_not_broken() -> None:
    assert jr.pnl_calendar([]) == {"months": [], "total": 0.0, "trades": 0, "days": 0}
    assert jr.pnl_calendar(None)["months"] == []
    undated = _row(pnl=5.0, entry_ms=None, exit_ms=None)
    assert jr.pnl_calendar([undated])["months"] == []
    assert jr.pnl_calendar(_calendar_set(), month="not a month")["months"] == []


# ══════════════════════════════════════════════════════════════
# the sentences
# ══════════════════════════════════════════════════════════════

def test_summary_sentences_name_the_headline_the_edge_and_the_risk() -> None:
    sentences = jr.summary_sentences(_tag_set())
    joined = " ".join(sentences)

    assert sentences[0].startswith("8 closed trades: 50.0% win rate")
    assert "expectancy +4.38 ticks a trade" in sentences[0]
    assert "profit factor 2.00" in sentences[0]
    assert "expectancy is +0.50R over 8 trades" in joined
    assert "average win +1.88R against average loss -0.88R" in joined
    assert "the edge is in the open-drive setups: 4 trades, +1.50R an average" in joined
    assert "the weakest setup is fade (3 trades, -1.00R an average)" in joined
    assert "longest losing run 4 trades;" in joined
    assert "deepest peak-to-trough 35.00 ticks" in joined
    assert len(sentences) <= jr.MAX_SENTENCES


def test_summary_sentences_never_call_the_untagged_bucket_an_edge() -> None:
    rows = [
        _row(entry=4500.0, exit_=4506.0, stop=4498.0, pnl=30.0),
        _row(entry=4500.0, exit_=4504.0, stop=4498.0, pnl=20.0, day=1),
        _row(entry=4500.0, exit_=4499.0, stop=4498.0, pnl=-5.0, day=2),
    ]

    joined = " ".join(jr.summary_sentences(rows))

    assert jr.UNTAGGED_GROUP not in joined
    assert "edge" not in joined                                           # one bucket is not an edge


def test_summary_sentences_say_so_when_no_row_records_a_stop() -> None:
    rows = [
        _row(entry=None, exit_=None, stop=None, pnl=10.0, rr=0.0),
        _row(entry=None, exit_=None, stop=None, pnl=-4.0, rr=0.0, day=1),
    ]

    joined = " ".join(jr.summary_sentences(rows))

    assert "no trade records a stop, so there is no R to average" in joined
    assert "R average" not in joined and "expectancy is" not in joined     # no R is claimed
    assert "2 closed trades" in joined


def test_summary_sentences_flag_the_planned_reward_risk_among_the_results() -> None:
    rows = [
        _row(entry=4500.0, exit_=4504.0, stop=4498.0, pnl=16.0),
        _row(entry=None, exit_=None, stop=None, pnl=5.0, rr=3.0, day=1),
    ]

    joined = " ".join(jr.summary_sentences(rows))

    assert "1 of the 2 R values came from the reward:risk the order was opened with" in joined


def test_summary_sentences_read_a_journal_where_nothing_worked() -> None:
    rows = [
        _row(entry=4500.0, exit_=4498.0, stop=4502.0, pnl=-10.0, extras={"setup": "fade"}),
        _row(entry=4500.0, exit_=4497.6, stop=4502.0, pnl=-12.0, day=1, extras={"setup": "fade"}),
        _row(entry=4500.0, exit_=4496.0, stop=4502.0, pnl=-18.0, day=2, extras={"setup": "reversal"}),
        _row(entry=4500.0, exit_=4497.0, stop=4502.0, pnl=-15.0, day=3, extras={"setup": "reversal"}),
    ]

    joined = " ".join(jr.summary_sentences(rows))

    assert "no setup group is positive — the least bad is" in joined
    assert "the edge is in" not in joined


def test_summary_sentences_read_the_journal_without_help_from_stats() -> None:
    alone = jr.summary_sentences(_r_set())
    handed = jr.summary_sentences(_r_set(), figures=jr.stats(_r_set()))

    assert alone == handed                                                # same rows, same words
    assert alone == jr.stats(_r_set())["sentences"]
    assert jr.summary_sentences([], figures=jr.stats([])) == \
        ["no closed trades yet — nothing here can be judged until a session ends."]


# ══════════════════════════════════════════════════════════════
# the statement
# ══════════════════════════════════════════════════════════════

def test_html_statement_gains_the_sentences_and_the_setup_table() -> None:
    rows = _tag_set()

    out = jr.html_statement(rows, jr.stats(rows), meta={"account": "test"})

    assert "<h2>What this says</h2>" in out
    assert "<h2>By setup</h2>" in out
    assert "the edge is in the open-drive setups" in out
    assert "open-drive" in out and "fade" in out
    assert "75.0%" in out                                                 # open-drive's win rate
    assert "1.50" in out                                                  # its average R
    assert "<h2>Summary</h2>" in out and "<h2>Daily</h2>" in out          # the old sections stay


def test_html_statement_keeps_a_hostile_tag_and_sentence_inert() -> None:
    rows = [_row(pnl=5.0, extras={"setup": "<script>alert(1)</script>"})]

    out = jr.html_statement(rows, jr.stats(rows), meta={"account": "test"})

    assert "<script" not in out.lower()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out
    assert "<link" not in out.lower() and "src=" not in out.lower()        # still self-contained


def test_html_statement_says_n_a_where_a_setup_group_has_no_r() -> None:
    rows = [_row(entry=None, exit_=None, stop=None, pnl=5.0, rr=0.0, extras={"setup": "no-stop-play"})]

    out = jr.html_statement(rows, jr.stats(rows), meta={"account": "test"})

    assert "no-stop-play" in out
    assert ">n/a<" in out                                                 # the group's average R
    assert "no trade records a stop" in out


def test_html_statement_still_renders_when_the_caller_passes_no_stats() -> None:
    bare = jr.html_statement([], None, meta=None)
    plain = jr.html_statement(_tag_set(), None, meta={"account": "test"})

    assert bare.startswith("<!DOCTYPE html>") and bare.rstrip().endswith("</html>")
    assert "no closed trades yet — nothing here can be judged until a session ends." in bare
    assert "No setup tags on these trades." in bare
    assert "the edge is in the open-drive setups" in plain


# ══════════════════════════════════════════════════════════════
# degradation on the path the app actually reads
# ══════════════════════════════════════════════════════════════

def test_extras_stay_narrow_on_the_database_path() -> None:
    """``desktop/api.py`` normalises rows before the analytics see them, so the optional fields the
    DB does not hold are absent — and every block says so instead of inventing a number."""
    served = jr.normalise_trades(_tag_set())

    assert all(set(row) == set(jr.TRADE_COLUMNS) for row in served)
    figures = jr.stats(served)

    assert figures["mae_mfe"]["count"] == 0
    assert [group["key"] for group in figures["by_setup"]] == [jr.UNTAGGED_GROUP]
    assert figures["r_count"] == 8                                        # R still comes from prices
    assert figures["calendar"]["months"]                                   # the days are still there
    assert all("mae" not in row["sub"].lower() for row in [{"sub": s} for s in figures["sentences"]])


def test_a_raw_tuple_row_reads_positionally_without_the_extras() -> None:
    tuple_row = (1, "ES", "LONG", DAY0_MS, DAY0_MS + 60_000, 4500.0, 4504.0, 4498.0, 4504.0, 16.0, 0.0, "[]", None)

    figures = jr.stats(jr.normalise_trades([tuple_row]))

    assert figures["count"] == 1 and figures["expectancy_r"] == pytest.approx(2.0)


# ══════════════════════════════════════════════════════════════
# the route the panel actually reads
# ══════════════════════════════════════════════════════════════

def test_the_journal_route_serves_the_deep_blocks_and_stays_strictly_serialisable(monkeypatch) -> None:
    """The panel reads ``payload.stats.*``, so the route's own serialisation is load-bearing.

    Starlette renders JSON with ``allow_nan=False``, and the fixture feeds the route a row whose
    numbers are ``NaN``/``inf`` — exactly how a poisoned import or a hand-edited row reaches the
    app. The figures block must survive that untouched (every number in it goes through
    ``_as_float``); the raw-row echo beside it does not, which the report raises for the parent.
    """
    import asyncio

    from orderflow_system.desktop import api as desktop_api

    rows = [{column: None for column in jr.TRADE_COLUMNS}, *[dict(row) for row in _tag_set()]]
    rows[0].update({"instrument": "ZZ", "direction": "long", "pnl_ticks": float("nan"),
                    "entry_price": float("inf"), "exit_price": float("-inf"), "profile_id": ""})
    monkeypatch.setattr(desktop_api, "_journal_rows", lambda limit=1000: rows)

    payload = asyncio.run(desktop_api.journal_view(limit=500))

    assert payload["ok"] is True and payload["count"] == len(rows)
    figures = payload["stats"]
    assert figures["by_setup"] and figures["calendar"]["months"]
    assert isinstance(figures["sentences"], list) and figures["sentences"]
    assert figures["expectancy_r"] == pytest.approx(0.5)

    encoded = json.dumps(figures, allow_nan=False)         # what Starlette's JSONResponse does
    assert "NaN" not in encoded and "Infinity" not in encoded


# ══════════════════════════════════════════════════════════════
# the panel: node, and the ledger it must not disturb
# ══════════════════════════════════════════════════════════════

def _node(*args: str) -> subprocess.CompletedProcess:
    exe = shutil.which("node") or "node"
    return subprocess.run([exe, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


def test_the_panel_parses_and_its_selftest_passes() -> None:
    assert JOURNAL_JS.is_file(), "desktop/ui/journal.js is missing"
    assert JOURNAL_SELFTEST.is_file(), "desktop/ui/journal.selftest.js is missing"

    check = _node("--check", str(JOURNAL_JS))
    assert check.returncode == 0, check.stderr
    run = _node(str(JOURNAL_SELFTEST))
    assert run.returncode == 0, (run.stdout or "") + (run.stderr or "")
    assert "0 failed" in run.stdout, run.stdout


def test_the_panel_adds_no_listener_and_no_timer_it_would_have_to_tear_down() -> None:
    """journal.js is on the frozen listener ledger at 1 add / 0 remove and owns no interval; the
    deep read hangs off the payload, so it must not change either number."""
    source = JOURNAL_JS.read_text(encoding="utf-8")

    assert source.count("addEventListener(") == 1
    assert "removeEventListener(" not in source
    assert "setInterval(" not in source


def test_the_two_halves_agree_on_the_block_names() -> None:
    """A rename in journal.py that the panel was not told about would blank the view silently."""
    source = JOURNAL_JS.read_text(encoding="utf-8")
    figures = jr.stats(_r_set())

    # every block the panel reads is in the payload the journal route serves
    for key in ("expectancy_r", "r_total", "r_count", "r_derived", "r_recorded", "r_stops",
                "payoff_ratio", "mae_mfe", "by_setup", "by_session", "calendar", "sentences"):
        assert key in figures, f"stats() no longer publishes {key}"
        assert key in source, f"journal.js never reads {key}"
    # and the names it reaches for inside those blocks
    for key in ("avg_mfe", "avg_mae", "peak", "months", "weeks", "win_rate", "avg_r",
                "profit_factor", "expectancy"):
        assert key in source, f"journal.js never reads {key}"


# ── §148 T3-F2/F3/F9/F11/F13 — the R cluster's honest-claims tail ────────────────────────────────


def test_a_stop_at_the_entry_yields_no_r_rather_than_the_plan() -> None:
    """§148 T3-F2 — the recorded fallback is the PLAN. A row whose own stop sits AT its entry
    records no risk, so it is answered with no R: the plan's number is not quoted as a result."""
    at_entry = _row(direction="long", entry=100.0, exit_=110.0, stop=100.0, pnl=20.0, rr=2.0)

    assert jr.r_of(at_entry) == {"r": None, "source": None}          # was {"r": 2.0, "recorded"}
    summary = jr.r_summary([at_entry])
    assert (summary["count"], summary["mean"], summary["total"]) == (0, None, None)

    # where nothing better exists (a row with no stop at all) the plan is still the last resort,
    # and is named as one
    planned = _row(direction="long", entry=None, exit_=None, stop=None, pnl=5.0, rr=3.0)
    assert jr.r_of(planned) == {"r": 3.0, "source": "recorded"}

    # a stop merely NEAR the entry is real risk and keeps its R
    near = _row(direction="long", entry=100.0, exit_=110.0, stop=99.5, pnl=20.0)
    assert jr.r_of(near) == {"r": 20.0, "source": "prices"}


def test_the_missing_r_sentence_says_what_the_rows_actually_record() -> None:
    """§148 T3-F3 — "no trade records a stop" was asserted from the absence of an R, even for rows
    that record one (an exit is missing, so no R falls out of it)."""
    stopped = [_row(direction="long", entry=4500.0, exit_=None, stop=4498.0, pnl=0.0)]

    lines = jr.summary_sentences(stopped)

    assert jr.stats(stopped)["r_stops"] == 1
    assert any("records a stop, but none yields an R" in line for line in lines), lines
    assert not any("no trade records a stop" in line for line in lines), lines

    # and a journal whose rows record NO stop keeps the plain sentence
    bare = [_row(direction="long", entry=4500.0, exit_=4504.0, stop=0.0, pnl=16.0, rr=0.0)]
    assert any("no trade records a stop" in line for line in jr.summary_sentences(bare))


def test_the_r_sentence_counts_trades_in_english() -> None:
    """§148 T3-F9 — the headline used ``_plural``; this line printed "over 1 trades"."""
    one = [_row(direction="long", entry=4500.0, exit_=4504.0, stop=4498.0, pnl=16.0)]

    line = next(text for text in jr.summary_sentences(one) if text.startswith("expectancy is"))
    assert line.startswith("expectancy is +2.00R over 1 trade.")

    two = one + [_row(direction="long", entry=4500.0, exit_=4504.0, stop=4498.0, pnl=16.0, day=1)]
    line = next(text for text in jr.summary_sentences(two) if text.startswith("expectancy is"))
    assert "over 2 trades." in line


def test_a_negative_stop_is_a_price_not_an_absence() -> None:
    """§148 T3-F11 — the writers' "no bracket" sentinel is an exact ``0.0``; a negative stop is a
    real price (a negative-priced spread, a backwardated commodity) and yields a real R."""
    row = _row(direction="long", entry=-100.0, exit_=-90.0, stop=-120.0, pnl=10.0)

    assert jr.r_of(row) == {"r": 0.5, "source": "prices"}            # risk 20, move +10

    # the sentinel still reads as no bracket — the row is not handed a zero-risk R
    sentinel = _row(direction="long", entry=100.0, exit_=110.0, stop=0.0, rr=3.0)
    assert jr.r_of(sentinel) == {"r": 3.0, "source": "recorded"}


def test_a_nested_signals_cell_reads_as_text_not_a_recursion_crash() -> None:
    """§148 T3-F4 — a 4,000-deep signals cell raised ``RecursionError`` out of ``stats()`` and the
    statement, and the panel's ``.catch`` swallowed the 500 into a blank view."""
    deep = "[" * 4000 + "]" * 4000
    row = _row(pnl=5.0, extras={"signals_json": deep})

    assert jr.setup_tags(row) == [deep]                     # the text stands in; no tag is invented
    figures = jr.stats([row])                               # and nothing raises
    assert figures["count"] == 1
    assert deep in jr.html_statement([row], figures, meta=None)


def test_derived_non_finite_figures_read_as_none_never_crash_the_render() -> None:
    """§148 T3-F5 — a sum of finite rows can still overflow (``fmean`` even raises).

    The row's claim was that the route's JSON render raises on one such figure; measured on the
    pre-fix build it does not — FastAPI's pydantic JSON serialiser maps a non-finite to ``null``
    (the same live payload read ``"total_pnl":null``) and every formatter reads it as "n/a". The
    contract pinned here is the one those renderers assume at the source: the analytics hand back a
    real number or ``None``, never an infinity for something downstream to notice. Declared in the
    register under §148 T3-F5.
    """
    rows = [_row(pnl=1e308), _row(pnl=9e307, day=1)]

    figures = jr.stats(rows)

    assert figures["gross_win"] is None and figures["total_pnl"] is None
    assert figures["expectancy"] is None                      # inf / 2 is still an infinity
    assert figures["count"] == 2 and figures["wins"] == 2     # the rows are still counted
    json.dumps(figures, allow_nan=False)                      # what a strict renderer would do with it

    # and one day's own sum overflows the same way (the route's `daily` block, built separately)
    assert jr.daily_series([_row(pnl=1e308), _row(pnl=9e307)])[0]["pnl"] is None

    # the R block's own sums are guarded the same way (fmean's OverflowError included)
    huge = [_row(pnl=5.0, entry=0.0, exit_=1e308, stop=-1.0),
            _row(pnl=5.0, entry=0.0, exit_=1e308, stop=-1.0, day=1)]
    r_figures = jr.stats(huge)

    assert r_figures["r_count"] == 2
    assert r_figures["r_total"] is None and r_figures["expectancy_r"] is None
    json.dumps(r_figures, allow_nan=False)


def test_a_short_sequence_is_not_read_as_a_trade() -> None:
    """§148 T3-F10 — any short sequence read positionally fabricated a trade out of its slots."""
    assert jr.normalise_trades([[1_700_000_000_000, 4500.0]]) == []
    assert jr.normalise_trades([[1, 2, 3]]) == []
    assert jr.normalise_trades([[]]) == []

    # the two shapes the positional fallback exists for still read: a full row, and a legacy row at
    # the width the journal had before the excursion columns (the pin two files over feeds one)
    full = tuple(_row().get(column) for column in jr.TRADE_COLUMNS)
    read = jr.normalise_trades([full])
    assert len(read) == 1 and read[0]["instrument"] == "ES" and read[0]["pnl_ticks"] == 16.0

    legacy = (1, "ES", "LONG", DAY0_MS, DAY0_MS + 60_000, 4500.0, 4504.0, 4498.0, 4504.0, 16.0, 0.0,
              "[]", None)
    read = jr.normalise_trades([legacy])
    assert len(read) == 1 and read[0]["pnl_ticks"] == 16.0
    assert jr.r_of(read[0]) == {"r": 2.0, "source": "prices"}


def test_the_capture_share_is_clamped_and_says_the_run_is_short() -> None:
    """§148 T3-F6 — a booked result past the recorded run read as "the exits kept 150.0% of the run"."""
    rows = [_row(pnl=6.0, extras={"mae_ticks": 1.0, "mfe_ticks": 4.0})]
    figures = jr.stats(rows)

    assert figures["mae_mfe"]["capture"] == 1.0             # never past the whole run
    assert figures["mae_mfe"]["capture_over"] is True       # and the payload says so
    text = " ".join(jr.summary_sentences(rows, figures=figures))
    assert "100.0% of the run" in text
    assert "shorter than the booked result" in text

    # a share inside the run is untouched and unflagged
    inside = jr.stats([_row(pnl=3.0, extras={"mae_ticks": 1.0, "mfe_ticks": 6.0})])
    assert inside["mae_mfe"]["capture"] == 0.5
    assert inside["mae_mfe"]["capture_over"] is False


def test_a_group_average_names_the_rows_it_rests_on() -> None:
    """§148 T3-F14 — an avg R of a group echoed the group's whole trade count, not the rows with an R."""
    rows = [
        _row(pnl=10.0, extras={"setup": "ORB"}, day=0),              # R +2.00 from its prices
        _row(pnl=10.0, extras={"setup": "ORB"}, day=1),
        _row(pnl=4.0, extras={"setup": "ORB"}, stop=None, rr=0.0, day=2),   # no stop: no R
        _row(pnl=-8.0, entry=4500.0, exit_=4494.0, stop=4498.0, extras={"setup": "DUD"}, day=3),
        _row(pnl=-8.0, entry=4500.0, exit_=4494.0, stop=4498.0, extras={"setup": "DUD"}, day=4),
    ]
    text = " ".join(jr.summary_sentences(rows, figures=jr.stats(rows)))

    assert "3 trades, 2 with an R" in text                  # ORB: the average rests on two of three
    assert "DUD (2 trades, -3.00R" in text                  # a group where every row has one says nothing extra


def test_a_month_key_is_normalised_and_an_unreadable_one_is_named() -> None:
    """§148 T3-F12 — "2023-1" and "2023-12-01" answered with a silent empty calendar."""
    plan = jr.pnl_calendar(_calendar_set(), month="2023-11")

    assert plan["months"] and plan["months"][0]["month"] == "2023-11"
    assert jr.pnl_calendar(_calendar_set(), month="2023-11-01")["months"] == plan["months"]

    january = jr.pnl_calendar(_calendar_set(), month="2023-1")     # a real month, just empty
    assert january["months"] == [] and "unknown_month" not in january

    bad = jr.pnl_calendar(_calendar_set(), month="not a month")
    assert bad["months"] == [] and bad["unknown_month"] == "not a month"
    assert bad["trades"] == 0 and bad["days"] == 0


def test_the_recorded_fallback_doc_names_the_one_live_writer() -> None:
    """§148 T3-F13 — the doc cited ``data.models.TradeState``, whose only path to the table
    (``data.database.log_trade``) has no callers: the doc now says so, and this pin holds it true."""
    doc = " ".join((jr.r_of.__doc__ or "").split())      # wrap-proof: the doc is prose, not markup
    assert "only live writer" in doc and "no callers" in doc

    root = Path(jr.__file__).resolve().parents[1]
    callers: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "def log_trade" in text:
            continue
        if "log_trade(" in text:
            callers.append(path.name)
    assert callers == [], f"log_trade gained callers ({callers}) — the docstring's claim is stale"
