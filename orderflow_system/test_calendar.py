"""The gate on the keyless economic calendar client (desktop/calendar.py) — no socket, ever.

The claim this file is about: the FF weekly feeds are loose — any cell can be missing, empty or
``null``, a holiday is an ordinary row, a date can be rubble — and the app still receives one clean,
UTC-anchored list, sorted, deduped across the two weekly files, or an ``ok: False`` sentence instead
of an exception. A stale cache is served only when it says it is stale.

What is pinned here, all of it against canned payloads and a fake opener (the module's one seam,
``opener(url, timeout)``):

* offset stamps normalised to the correct UTC epoch milliseconds (``08:30-04:00`` is ``12:30Z``);
* missing / ``null`` / empty cells become ``""`` (and ``unknown`` impact), never a crash;
* a holiday row keeps its own impact, and an unreadable date skips that row and only that row;
* both URLs are fetched, the boundary-week duplicate is merged once (and the richer copy wins);
* the default transport (no opener injected) is ``urlopen`` carrying the declared User-Agent — the
  bare urllib agent is the one this host 403s;
* an HTTP error, a non-JSON body and a non-list body come back as ``ok: False`` / an ``error``
  sentence — a dead feed never raises, and a dead feed does not take the live one down with it;
* the cache: written atomically with exactly the four payload keys, served inside the ttl without
  touching the wire, refreshed once expired, and served as ``stale: True`` (with the reason) when
  the fetch fails — an absent or corrupt cache is an honest failure, not an exception;
* the pure filters — ``upcoming``'s window/impact/currency rules, ``due_alerts``' lead window and
  once-only keys — and the exact alert wording of ``event_message``.

Run:  .venv/Scripts/python.exe -m pytest orderflow_system/test_calendar.py -q
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from orderflow_system.desktop import calendar as cal

THIS_URL, NEXT_URL = cal.FEED_URLS

#: The feed's real shape: ``2026-09-18T08:30:00-04:00`` — an offset stamp, not a bare one.
FED_AT = dt.datetime(2026, 9, 18, 12, 30, tzinfo=dt.timezone.utc)
FED_MS = int(FED_AT.timestamp()) * 1000
NOW_MS = FED_MS

FED_ROW: dict[str, Any] = {
    "title": "Federal Funds Rate",
    "country": "USD",
    "date": "2026-09-18T08:30:00-04:00",
    "impact": "High",
    "forecast": "4.25%",
    "previous": "4.50%",
}


def _fed_row(**overrides: Any) -> dict[str, Any]:
    return {**FED_ROW, **overrides}


def _payload(*rows: Any) -> bytes:
    """A feed body as the host serves it: a JSON list, UTF-8, possibly with rubbish in it."""
    return json.dumps(list(rows)).encode("utf-8")


def _opener_for(**bodies: bytes) -> tuple[Any, list[tuple[str, Any]]]:
    """An opener serving canned bodies per URL; an unlisted URL is a URLError, like a real miss."""
    calls: list[tuple[str, Any]] = []

    def opener(url: str, timeout: Any = None) -> bytes:
        calls.append((url, timeout))
        if url not in bodies:
            raise urllib.error.URLError(f"no canned payload for {url}")
        return bodies[url]

    return opener, calls


def _failing_opener(exc: BaseException | None = None) -> tuple[Any, list[tuple[str, Any]]]:
    calls: list[tuple[str, Any]] = []

    def opener(url: str, timeout: Any = None) -> bytes:
        calls.append((url, timeout))
        raise exc if exc is not None else urllib.error.URLError("connection refused")

    return opener, calls


class FakeResponse:
    """The ``urlopen`` shape: not bytes in hand but an object that must be read (and closed)."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.closed = False

    def read(self) -> bytes:
        chunk, self._payload = self._payload, b""
        return chunk

    def close(self) -> None:
        self.closed = True


def _feeds(this_week: bytes | None = None, next_week: bytes | None = None) -> Any:
    """An opener with both weekly files answered (an empty week is a valid answer)."""
    return _opener_for(**{THIS_URL: this_week or b"[]", NEXT_URL: next_week or b"[]"})


def _event(offset_min: float, **overrides: Any) -> dict[str, Any]:
    """A normalised event ``offset_min`` minutes from ``NOW_MS`` (negative = already past)."""
    event: dict[str, Any] = {
        "at_ms": NOW_MS + int(offset_min * 60_000),
        "currency": "USD",
        "impact": "high",
        "title": "Release",
        "country": "USD",
        "forecast": "",
        "previous": "",
        "actual": "",
    }
    event.update(overrides)
    return event


# ══════════════════════════════════════════════════════════════
# The feed contract
# ══════════════════════════════════════════════════════════════

def test_the_two_urls_are_the_keyless_weekly_files() -> None:
    assert cal.FEED_URLS == (
        "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
    )


def test_happy_path_normalises_an_offset_stamp_to_utc_ms() -> None:
    opener, calls = _feeds(this_week=_payload(_fed_row()))

    result = cal.fetch_events(opener=opener, now=1_700_000_000.0)

    assert result["ok"] is True
    assert result["error"] == ""
    assert result["fetched_at_ms"] == 1_700_000_000_000
    assert calls == [(THIS_URL, cal.DEFAULT_TIMEOUT_S), (NEXT_URL, cal.DEFAULT_TIMEOUT_S)]
    assert result["events"] == [
        {
            "at_ms": FED_MS,
            "currency": "USD",
            "impact": "high",
            "title": "Federal Funds Rate",
            "country": "USD",
            "forecast": "4.25%",
            "previous": "4.50%",
            "actual": "",
        }
    ]
    # 08:30 at -04:00 really is 12:30 UTC — the offset was applied, not ignored.
    stamp = dt.datetime.fromtimestamp(FED_MS / 1000, tz=dt.timezone.utc)
    assert stamp.isoformat() == "2026-09-18T12:30:00+00:00"


def test_the_timeout_reaches_the_opener() -> None:
    opener, calls = _feeds()

    cal.fetch_events(opener=opener, now=1_700_000_000.0, timeout=3.5)

    assert [timeout for _, timeout in calls] == [3.5, 3.5]


def test_an_opener_may_return_a_urlopen_style_response() -> None:
    inner, _ = _feeds(this_week=_payload(_fed_row()))

    def opener(url: str, timeout: Any = None) -> FakeResponse:
        return FakeResponse(inner(url, timeout=timeout))

    result = cal.fetch_events(opener=opener, now=1_700_000_000.0)

    assert result["ok"] is True
    assert [event["at_ms"] for event in result["events"]] == [FED_MS]


def test_the_default_transport_carries_the_declared_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """No opener injected: ``urlopen`` is used, with the agent the host does not 403 (measured)."""
    seen: list[tuple[str, Any, Any]] = []

    def fake_urlopen(request: Any, timeout: Any = None) -> FakeResponse:
        seen.append((request.full_url, request.get_header("User-agent"), timeout))
        return FakeResponse(_payload(_fed_row()) if request.full_url == THIS_URL else b"[]")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = cal.fetch_events(now=1_700_000_000.0, timeout=4.0)

    assert result["ok"] is True
    assert [url for url, _, _ in seen] == [THIS_URL, NEXT_URL]
    assert {agent for _, agent, _ in seen} == {cal.APP_USER_AGENT}
    assert [timeout for _, _, timeout in seen] == [4.0, 4.0]
    assert cal.APP_USER_AGENT.strip() and "python" not in cal.APP_USER_AGENT.lower()


def test_missing_empty_and_null_cells_are_tolerated() -> None:
    bare = {"country": "eur", "date": "2026-09-18T12:30:00Z"}  # no title, no impact, no figures
    empty = {
        "title": "GDP m/m",
        "country": "",
        "date": "2026-09-18T09:00:00Z",
        "impact": "",
        "forecast": None,
        "previous": 0.2,
        "actual": "",
    }
    opener, _ = _feeds(this_week=_payload(bare, empty))

    result = cal.fetch_events(opener=opener, now=1_700_000_000.0)

    assert result["ok"] is True
    gdp, loose = result["events"]  # sorted by time: 09:00Z ahead of 12:30Z
    assert loose == {
        "at_ms": FED_MS,
        "currency": "EUR",
        "impact": "unknown",
        "title": "",
        "country": "eur",
        "forecast": "",
        "previous": "",
        "actual": "",
    }
    assert (loose["currency"], loose["country"]) == ("EUR", "eur")
    assert gdp["title"] == "GDP m/m"
    assert (gdp["currency"], gdp["country"]) == ("", "")
    assert gdp["impact"] == "unknown"
    assert gdp["previous"] == "0.2"  # a number in a text cell is not a crash
    assert gdp["at_ms"] == FED_MS - 3_600_000 * 3 - 1_800_000  # 09:00Z, i.e. 12:30Z minus 3.5 h


def test_a_holiday_row_keeps_its_own_impact() -> None:
    holiday = {
        "title": "Bank Holiday",
        "country": "JPY",
        "date": "2026-09-21T00:00:00+09:00",
        "impact": "Holiday",
        "forecast": "",
        "previous": "",
        "actual": "",
    }
    opener, _ = _feeds(this_week=_payload(holiday))

    event = cal.fetch_events(opener=opener, now=1_700_000_000.0)["events"][0]

    assert event["impact"] == "holiday"
    assert cal.impact_rank(event["impact"]) == 0
    assert event["at_ms"] == int(dt.datetime(2026, 9, 20, 15, 0, tzinfo=dt.timezone.utc).timestamp()) * 1000


@pytest.mark.parametrize(
    "date",
    ["not-a-date", "", "   ", None, "2026-13-45T99:99:99", {"y": 2026}, True],
)
def test_rows_with_an_unreadable_date_are_skipped(date: Any) -> None:
    opener, _ = _feeds(this_week=_payload(_fed_row(), _fed_row(title="Rubble", date=date)))

    result = cal.fetch_events(opener=opener, now=1_700_000_000.0)

    assert result["ok"] is True
    assert [event["title"] for event in result["events"]] == ["Federal Funds Rate"]


def test_a_row_that_is_not_an_object_is_skipped_not_fatal() -> None:
    body = json.dumps([1, "nope", None, ["list"], _fed_row()]).encode("utf-8")
    opener, _ = _feeds(this_week=body)

    result = cal.fetch_events(opener=opener, now=1_700_000_000.0)

    assert result["ok"] is True
    assert [event["title"] for event in result["events"]] == ["Federal Funds Rate"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-09-18T08:30:00-04:00", FED_MS),
        ("2026-09-18T12:30:00Z", FED_MS),
        ("2026-09-18T12:30:00+00:00", FED_MS),
        ("2026-09-18T12:30:00", FED_MS),  # a bare stamp is read as UTC, never as the host's zone
        (1_789_734_600, FED_MS),
        (1_789_734_600.0, FED_MS),
        ("1789734600", FED_MS),
        (1_789_734_600_000, FED_MS),
        ("", None),
        (None, None),
        (True, None),
        ("soon", None),
    ],
)
def test_a_stamp_and_the_epoch_ms_it_means(value: Any, expected: int | None) -> None:
    assert cal.parse_at_ms(value) == expected


# ══════════════════════════════════════════════════════════════
# Merge, dedupe, sort
# ══════════════════════════════════════════════════════════════

def test_both_feeds_are_merged_deduped_and_sorted() -> None:
    cpi = _fed_row(title="CPI m/m", country="GBP", date="2026-09-18T07:00:00-04:00", impact="Medium")
    later = _fed_row(title="ISM Services PMI", date="2026-09-19T10:00:00-04:00", impact="Low")
    # The same release appears in both weekly files near the boundary; next week's copy carries the
    # published actual, which the first copy did not have.
    this_week = _payload(later, _fed_row(), cpi)
    next_week = _payload(
        _fed_row(actual="4.25%", impact="High"),
        _fed_row(title="ECB Presser", country="EUR", date="2026-09-24T08:15:00+02:00"),
    )

    opener, _ = _feeds(this_week=this_week, next_week=next_week)
    result = cal.fetch_events(opener=opener, now=1_700_000_000.0)

    assert result["ok"] is True
    assert [event["title"] for event in result["events"]] == ["CPI m/m", "Federal Funds Rate", "ISM Services PMI", "ECB Presser"]
    assert [event["at_ms"] for event in result["events"]] == sorted(event["at_ms"] for event in result["events"])
    fed = next(event for event in result["events"] if event["title"] == "Federal Funds Rate")
    assert fed["actual"] == "4.25%"  # the richer duplicate won, and there is exactly one of it


def test_a_duplicate_whose_impact_is_unknown_does_not_erase_the_known_one() -> None:
    this_week = _payload(_fed_row(impact=""))
    next_week = _payload(_fed_row())

    opener, _ = _feeds(this_week=this_week, next_week=next_week)
    result = cal.fetch_events(opener=opener, now=1_700_000_000.0)

    assert len(result["events"]) == 1
    assert result["events"][0]["impact"] == "high"


# ══════════════════════════════════════════════════════════════
# Failure is data
# ══════════════════════════════════════════════════════════════

def test_a_total_failure_is_reported_and_never_raised() -> None:
    opener, calls = _failing_opener()

    result = cal.fetch_events(opener=opener, now=1_700_000_000.0)

    assert result["ok"] is False
    assert result["events"] == []
    assert "connection refused" in result["error"]
    assert result["fetched_at_ms"] == 1_700_000_000_000
    assert len(calls) == 2  # both feeds were attempted, not just the first


def test_an_http_error_is_a_sentence_not_a_traceback() -> None:
    http_429 = urllib.error.HTTPError(THIS_URL, 429, "Too Many Requests", None, None)
    opener, _ = _failing_opener(http_429)

    result = cal.fetch_events(opener=opener, now=1_700_000_000.0)

    assert result["ok"] is False
    assert "HTTPError" in result["error"]
    assert "429" in result["error"]


def test_one_dead_feed_still_serves_the_live_one() -> None:
    opener, _ = _opener_for(**{THIS_URL: b"<html>403 Forbidden</html>", NEXT_URL: _payload(_fed_row())})

    result = cal.fetch_events(opener=opener, now=1_700_000_000.0)

    assert result["ok"] is True
    assert [event["title"] for event in result["events"]] == ["Federal Funds Rate"]
    assert THIS_URL in result["error"]  # the failure is reported, not swallowed


def test_a_body_that_is_not_a_list_of_rows_is_an_error() -> None:
    opener, _ = _opener_for(**{THIS_URL: b'{"row": 1}', NEXT_URL: b'"nope"'})

    result = cal.fetch_events(opener=opener, now=1_700_000_000.0)

    assert result["ok"] is False
    assert "list" in result["error"]


def test_an_opener_returning_rubbish_is_an_error_not_a_crash() -> None:
    def opener(url: str, timeout: Any = None) -> object:
        return object()

    result = cal.fetch_events(opener=opener, now=1_700_000_000.0)

    assert result["ok"] is False
    assert "object" in result["error"]


def test_an_empty_week_is_a_successful_fetch() -> None:
    opener, _ = _feeds()

    result = cal.fetch_events(opener=opener, now=1_700_000_000.0)

    assert (result["ok"], result["events"], result["error"]) == (True, [], "")


def test_the_clock_may_be_a_callable_or_a_datetime() -> None:
    opener, _ = _feeds()

    from_callable = cal.fetch_events(opener=opener, now=lambda: 1_700_000_000.0)
    from_datetime = cal.fetch_events(opener=opener, now=FED_AT)

    assert from_callable["fetched_at_ms"] == 1_700_000_000_000
    assert from_datetime["fetched_at_ms"] == FED_MS


# ══════════════════════════════════════════════════════════════
# The cache
# ══════════════════════════════════════════════════════════════

def test_a_good_fetch_is_cached_and_reused_without_the_wire(tmp_path: Path) -> None:
    cache = tmp_path / "calendar.json"
    good, _ = _feeds(this_week=_payload(_fed_row()))

    first = cal.fetch_events_cached(cache, opener=good, now=1_700_000_000.0)

    assert (first["ok"], first["stale"], first["cache_age_s"]) == (True, False, 0.0)
    stored = json.loads(cache.read_text(encoding="utf-8"))
    assert set(stored) == {"ok", "events", "error", "fetched_at_ms"}  # transport shape is not persisted
    assert stored["fetched_at_ms"] == 1_700_000_000_000
    assert [event["title"] for event in stored["events"]] == ["Federal Funds Rate"]

    # Two hours later, inside the 4 h ttl: the cache answers and the opener is never called.
    boom, boom_calls = _failing_opener()
    second = cal.fetch_events_cached(cache, opener=boom, now=1_700_000_000.0 + 7200.0)

    assert boom_calls == []
    assert (second["ok"], second["stale"], second["cache_age_s"]) == (True, False, 7200.0)
    assert [event["title"] for event in second["events"]] == ["Federal Funds Rate"]


def test_an_expired_cache_is_refetched_and_replaced(tmp_path: Path) -> None:
    cache = tmp_path / "calendar.json"
    good, _ = _feeds(this_week=_payload(_fed_row()))
    cal.fetch_events_cached(cache, opener=good, now=1_700_000_000.0)

    later = 1_700_000_000.0 + cal.DEFAULT_TTL_S + 1.0
    second_opener, second_calls = _feeds(this_week=_payload(_fed_row(actual="4.25%")))
    second = cal.fetch_events_cached(cache, opener=second_opener, now=later)

    assert len(second_calls) == 2  # past the ttl the wire is touched again
    assert (second["ok"], second["stale"], second["cache_age_s"]) == (True, False, 0.0)
    assert json.loads(cache.read_text(encoding="utf-8"))["fetched_at_ms"] == int(later * 1000.0)


def test_a_failed_fetch_serves_the_cache_and_says_it_is_stale(tmp_path: Path) -> None:
    cache = tmp_path / "calendar.json"
    good, _ = _feeds(this_week=_payload(_fed_row()))
    cal.fetch_events_cached(cache, opener=good, now=1_700_000_000.0)

    boom, boom_calls = _failing_opener(urllib.error.HTTPError(NEXT_URL, 503, "Service Unavailable", None, None))
    later = 1_700_000_000.0 + cal.DEFAULT_TTL_S + 60.0
    stale = cal.fetch_events_cached(cache, opener=boom, now=later)

    assert len(boom_calls) == 2
    assert stale["ok"] is True  # the events are still worth showing…
    assert stale["stale"] is True  # …but the panel has to say they may be out of date
    assert "503" in stale["error"]
    assert stale["cache_age_s"] == cal.DEFAULT_TTL_S + 60.0
    assert [event["title"] for event in stale["events"]] == ["Federal Funds Rate"]


def test_a_failure_with_no_cache_is_an_honest_failure(tmp_path: Path) -> None:
    cache = tmp_path / "missing.json"
    boom, _ = _failing_opener()

    result = cal.fetch_events_cached(cache, opener=boom, now=1_700_000_000.0)

    assert (result["ok"], result["stale"], result["events"], result["cache_age_s"]) == (False, False, [], None)
    assert result["error"]
    assert not cache.exists()  # a failed fetch never writes a cache


def test_a_corrupt_cache_is_ignored_and_healed(tmp_path: Path) -> None:
    cache = tmp_path / "calendar.json"
    cache.write_text("{not json at all", encoding="utf-8")
    boom, _ = _failing_opener()

    broken = cal.fetch_events_cached(cache, opener=boom, now=1_700_000_000.0)
    assert broken["ok"] is False  # rubbish on disk is not a calendar

    good, _ = _feeds(this_week=_payload(_fed_row()))
    healed = cal.fetch_events_cached(cache, opener=good, now=1_700_000_000.0)

    assert healed["ok"] is True
    assert json.loads(cache.read_text(encoding="utf-8"))["ok"] is True


def test_ttl_zero_forces_a_fetch_even_with_a_fresh_cache(tmp_path: Path) -> None:
    cache = tmp_path / "calendar.json"
    good, _ = _feeds(this_week=_payload(_fed_row()))
    cal.fetch_events_cached(cache, opener=good, now=1_700_000_000.0)

    forced, forced_calls = _feeds(this_week=_payload(_fed_row(actual="4.25%")))
    result = cal.fetch_events_cached(cache, opener=forced, now=1_700_000_000.0, ttl_s=0)

    assert len(forced_calls) == 2
    assert result["events"][0]["actual"] == "4.25%"


def test_the_cache_directory_is_created_when_missing(tmp_path: Path) -> None:
    cache = tmp_path / "deep" / "nested" / "calendar.json"
    good, _ = _feeds(this_week=_payload(_fed_row()))

    result = cal.fetch_events_cached(cache, opener=good, now=1_700_000_000.0)

    assert result["ok"] is True
    assert cache.exists()


# ══════════════════════════════════════════════════════════════
# The pure filters
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    ("impact", "rank"),
    [
        ("High", 3),
        ("medium", 2),
        ("MODERATE", 2),
        ("Low", 1),
        ("Holiday", 0),
        ("Bank Holiday", 0),
        ("", 0),
        (None, 0),
        ("nonsense", 0),
    ],
)
def test_impact_rank_orders_the_vocabulary(impact: Any, rank: int) -> None:
    assert cal.impact_rank(impact) == rank


def test_upcoming_applies_the_window_and_the_impact_floor() -> None:
    events = [
        _event(-60, title="Gone"),
        _event(30, impact="medium", title="Mid"),
        _event(120, title="NFP"),
        _event(25 * 60, title="Next week"),
    ]

    picked = cal.upcoming(events, now_ms=NOW_MS)

    assert [event["title"] for event in picked] == ["NFP"]
    # Both ends of the window are inclusive, and the result comes back in time order.
    edge_cases = [_event(240, title="Late"), _event(0, title="Now"), _event(24 * 60, title="Edge")]
    edges = cal.upcoming(edge_cases, now_ms=NOW_MS)
    assert [event["title"] for event in edges] == ["Now", "Late", "Edge"]
    # A lower floor and a wider window let the rest through.
    wider = cal.upcoming(events, now_ms=NOW_MS, within_hours=48, min_impact="medium")
    assert [event["title"] for event in wider] == ["Mid", "NFP", "Next week"]


def test_upcoming_currency_filter_is_case_insensitive_and_optional() -> None:
    events = [
        _event(60, currency="USD", title="NFP"),
        _event(90, currency="eur", title="ECB"),
        _event(120, currency="JPY", title="BoJ"),
    ]

    assert [event["title"] for event in cal.upcoming(events, now_ms=NOW_MS, currencies=["usd"])] == ["NFP"]
    assert {event["currency"] for event in cal.upcoming(events, now_ms=NOW_MS, currencies=["EUR", "jpy"])} == {"eur", "JPY"}
    assert len(cal.upcoming(events, now_ms=NOW_MS)) == 3
    assert [event["currency"] for event in cal.upcoming(events, now_ms=NOW_MS, currencies="eur")] == ["eur"]
    assert cal.upcoming(events, now_ms=NOW_MS, currencies=[]) == sorted(events, key=lambda event: event["at_ms"])


def test_upcoming_ignores_rows_that_are_not_events() -> None:
    events: list[Any] = ["nope", None, 3, {"at_ms": "when?"}, _event(60, title="NFP")]

    assert [event["title"] for event in cal.upcoming(events, now_ms=NOW_MS)] == ["NFP"]


def test_due_alerts_honours_the_lead_window_and_fires_once() -> None:
    soon = _event(5, title="NFP")
    later = _event(20, title="CPI")
    past = _event(-5, title="Old")
    events = [later, past, soon]

    due = cal.due_alerts(events, now_ms=NOW_MS, lead_minutes=15.0)

    assert [event["title"] for event in due] == ["NFP"]
    # The key the caller stores once the alert has gone out is the documented one.
    key = cal.event_key(soon)
    assert key == f"USD|NFP|{soon['at_ms']}"
    assert cal.due_alerts(events, now_ms=NOW_MS, lead_minutes=15.0, alerted_keys={key}) == []
    # An event starting now or exactly at the end of the lead is due; a wider lead admits the next one.
    assert [event["title"] for event in cal.due_alerts(events, now_ms=NOW_MS, lead_minutes=20.0, alerted_keys=[])] == [
        "NFP",
        "CPI",
    ]
    assert [event["title"] for event in cal.due_alerts([_event(0, title="Now")], now_ms=NOW_MS, lead_minutes=0.0)] == ["Now"]
    assert cal.due_alerts(events, now_ms=NOW_MS, lead_minutes=15.0) == due  # still pure on the second call


def test_event_message_is_the_line_the_alert_sends() -> None:
    fed = {
        "at_ms": FED_MS,
        "currency": "USD",
        "impact": "high",
        "title": "Federal Funds Rate",
        "country": "USD",
        "forecast": "4.25%",
        "previous": "4.50%",
        "actual": "",
    }

    assert cal.event_message(fed) == (
        "USD · Federal Funds Rate — high impact at 12:30 UTC (forecast 4.25%, previous 4.50%)"
    )
    assert cal.event_message({**fed, "actual": "4.00%"}) == (
        "USD · Federal Funds Rate — high impact at 12:30 UTC (actual 4.00%, forecast 4.25%, previous 4.50%)"
    )


def test_event_message_omits_absent_figures_and_names_a_holiday() -> None:
    midnight = int(dt.datetime(2026, 9, 21, tzinfo=dt.timezone.utc).timestamp()) * 1000
    holiday = _event(0, at_ms=midnight, currency="JPY", impact="Holiday", title="Bank Holiday")

    assert cal.event_message(holiday) == "JPY · Bank Holiday — holiday impact at 00:00 UTC"
    assert cal.event_message({"at_ms": FED_MS, "currency": "usd", "impact": "High"}) == (
        "USD · Unnamed event — high impact at 12:30 UTC"
    )
    assert cal.event_message({"currency": "USD", "impact": "High", "title": "No date"}) == (
        "USD · No date — high impact at an unknown time"
    )
