"""
Tests for Finnhub feed — transport injection makes these offline-safe.
"""

from __future__ import annotations


from orderflow_system.data.finnhub_feed import (
    FinnhubFeed,
    Calendar,
    CalendarEvent,
    NewsBatch,
    NewsItem,
    _map_status,
    to_calendar_rows,
    to_news_items,
)


def _mock_transport(status, body):
    def transport(method, url, headers, params, timeout):
        return (status, {}, body)
    return transport


# ── FinnhubError ─────────────────────────────────────────────────────────────────

class TestFinnhubError:
    def test_401_is_fatal(self):
        err = _map_status(401)
        assert err.fatal is True

    def test_429_is_not_fatal(self):
        err = _map_status(429)
        assert err.fatal is False


# ── _map_status ──────────────────────────────────────────────────────────────────

class TestMapStatus:
    def test_401(self):
        err = _map_status(401)
        assert err.status == 401
        assert err.fatal is True

    def test_429(self):
        err = _map_status(429)
        assert err.status == 429
        assert err.fatal is False

    def test_500(self):
        err = _map_status(500)
        assert err.fatal is True


# ── the app-shape adapters (§146) ────────────────────────────────────────────────
#
# `to_calendar_rows` / `to_news_items` are the two pure functions the app's own routes call, and
# they are where a payload becomes a row the Calendar view / News panel can print. Pinned here:
# the priority→impact mapping, the country that stands in for a currency code, the refusal to
# invent a clock, and the headline shape (a link that is really a URL or nothing at all).


def _event(**kw) -> CalendarEvent:
    base = dict(category="forex", title="US CPI", timestamp_ms=1_760_000_000_000, priority=1,
                country="US", actual="3.7%", consensus="3.6%", previous="3.4%")
    base.update(kw)
    return CalendarEvent(**base)


class TestCalendarRows:
    def test_priority_becomes_the_calendar_impact_vocabulary(self):
        impacts = [to_calendar_rows([_event(priority=p)])[0]["impact"] for p in (1, 2, 3)]
        assert impacts == ["high", "medium", "low"]

    def test_an_unknown_priority_is_unknown_not_high(self):
        assert to_calendar_rows([_event(priority=9)])[0]["impact"] == "unknown"
        assert to_calendar_rows([_event(priority=None)])[0]["impact"] == "unknown"

    def test_the_country_stands_in_for_the_currency_code(self):
        row = to_calendar_rows([_event(country="eu")])[0]
        assert row["currency"] == "EU" and row["country"] == "eu"

    def test_a_row_with_no_clock_is_dropped(self):
        assert to_calendar_rows([_event(timestamp_ms=None)]) == []
        assert to_calendar_rows([_event(timestamp_ms=0), _event(timestamp_ms=None)])[0]["at_ms"] == 0

    def test_a_row_with_no_title_is_dropped(self):
        assert to_calendar_rows([_event(title="   ")]) == []

    def test_the_desk_numbers_travel_as_strings(self):
        row = to_calendar_rows([_event()])[0]
        assert row["forecast"] == "3.6%" and row["previous"] == "3.4%" and row["actual"] == "3.7%"
        assert to_calendar_rows([_event(consensus=None)])[0]["forecast"] == ""

    def test_junk_entries_are_skipped_rather_than_guessed(self):
        assert to_calendar_rows([None, "nonsense", _event()]) == [to_calendar_rows([_event()])[0]]
        assert to_calendar_rows(None) == []


class TestNewsItems:
    def _batch(self, items) -> NewsBatch:
        return NewsBatch(items=items)

    def test_an_item_becomes_the_panel_shape(self):
        item = NewsItem(headline="Fed holds rates", source="Benzinga",
                        url="https://finnhub.io/a", published_ms=1_760_000_000_000)
        row = to_news_items(self._batch([item]))[0]
        assert row["title"] == "Fed holds rates"
        assert row["link"] == "https://finnhub.io/a"
        assert row["source"] == "Benzinga"
        assert row["published_ms"] == 1_760_000_000_000

    def test_a_headline_with_no_title_is_dropped(self):
        assert to_news_items(self._batch([NewsItem(headline="  ", url="https://x.example/a")])) == []

    def test_a_link_that_is_not_a_url_is_left_empty(self):
        rows = to_news_items(self._batch([
            NewsItem(headline="A", url="javascript:alert(1)"),
            NewsItem(headline="B", url=""),
        ]))
        assert [r["link"] for r in rows] == ["", ""]

    def test_a_missing_publisher_falls_back_to_the_lane_label(self):
        row = to_news_items(self._batch([NewsItem(headline="A", url="https://x.example/a")]),
                            fallback_source="finnhub")[0]
        assert row["source"] == "finnhub"

    def test_an_empty_batch_is_an_empty_list(self):
        assert to_news_items(None) == []
        assert to_news_items(self._batch([])) == []


class TestCalendarCountry:
    def test_the_parse_carries_the_country_through(self):
        body = ('[{"category": "forex", "title": "US CPI", "timestamp": 1700000000, '
                '"priority": 1, "country": "US"}]')
        cal = FinnhubFeed(api_key="k", transport=_mock_transport(200, body)).calendar()
        assert cal.events[0].country == "US"
        assert to_calendar_rows(cal.events)[0]["currency"] == "US"

    def test_a_missing_country_is_none_not_a_guess(self):
        body = '[{"category": "forex", "title": "X", "timestamp": 1700000000, "priority": 1}]'
        cal = FinnhubFeed(api_key="k", transport=_mock_transport(200, body)).calendar()
        assert cal.events[0].country is None
        assert to_calendar_rows(cal.events)[0]["currency"] == ""


class TestFinnhubFeed:
    def test_empty_key_returns_no_auth(self):
        feed = FinnhubFeed(api_key="",
                           transport=_mock_transport(200, "[]"))
        cal = feed.calendar()
        assert isinstance(cal, Calendar)
        assert cal.error is None or cal.error == ""

    def test_401_is_fatal(self):
        feed = FinnhubFeed(api_key="bad",
                           transport=_mock_transport(401, "Unauthorized"))
        cal = feed.calendar()
        assert cal.error is not None
        assert "key" in cal.error.lower()

    def test_429_returns_error(self):
        feed = FinnhubFeed(api_key="k",
                           transport=_mock_transport(429, "Rate limited"))
        cal = feed.calendar()
        assert cal.error is not None
        assert "rate" in cal.error.lower()

    def test_calendar_parses_list_response(self):
        body = (
            '[{"category": "forex", "title": "US CPI Release", '
            '"description": "Consumer Price Index", "source": "BLS", '
            '"url": "https://example.com", "timezone": "America/New_York", '
            '"date": "2026-09-18", "time": "08:30", "timestamp": 1700000000, '
            '"priority": 1, "actual": "3.7%", "consensus": "3.6%", "previous": "3.4%"},'
            '{"category": "indices", "title": "FOMC Decision", '
            '"timestamp": 1700000000, "priority": 1}]'
        )
        feed = FinnhubFeed(api_key="k",
                           transport=_mock_transport(200, body))
        cal = feed.calendar()
        assert cal.error is None
        assert len(cal.events) == 2

        e1 = cal.events[0]
        assert e1.category == "forex"
        assert e1.title == "US CPI Release"
        assert e1.priority == 1
        assert e1.actual == "3.7%"

        e2 = cal.events[1]
        assert e2.category == "indices"
        assert e2.title == "FOMC Decision"
        assert e2.actual is None

    def test_calendar_parses_dict_response(self):
        body = (
            '{"calendar": [{"title": "Test Event", "timestamp": 1700000000}]}'
        )
        feed = FinnhubFeed(api_key="k",
                           transport=_mock_transport(200, body))
        cal = feed.calendar()
        assert len(cal.events) == 1
        assert cal.events[0].title == "Test Event"

    def test_news_parses_list_response(self):
        body = (
            '[{"category": "general", "headline": "Markets rally on rate cut hopes", '
            '"summary": "Equities surge after Fed signal.", "source": "Reuters", '
            '"url": "https://example.com", "image": "https://example.com/img.jpg", '
            '"datetime": 1700000000, "related": "SPY"}]'
        )
        feed = FinnhubFeed(api_key="k",
                           transport=_mock_transport(200, body))
        news = feed.news()
        assert news.error is None
        assert len(news.items) == 1

        item = news.items[0]
        assert item.headline == "Markets rally on rate cut hopes"
        assert item.source == "Reuters"
        assert item.associated_stock == "SPY"
        assert item.published_ms == 1700000000000

    def test_news_parses_dict_response(self):
        body = (
            '{"news": [{"headline": "Test", "datetime": 1700000000}]}'
        )
        feed = FinnhubFeed(api_key="k",
                           transport=_mock_transport(200, body))
        news = feed.news()
        assert len(news.items) == 1
        assert news.items[0].headline == "Test"

    def test_malformed_json_returns_error(self):
        feed = FinnhubFeed(api_key="k",
                           transport=_mock_transport(200, "not json"))
        cal = feed.calendar()
        assert cal.error is not None
        assert "malformed" in cal.error.lower()

    def test_status(self):
        feed = FinnhubFeed(api_key="k",
                           transport=_mock_transport(200, "[]"))
        feed.calendar()
        s = feed.status()
        assert s["source"] == "finnhub"
        assert s["key_configured"] is True


# ── _num helper ──────────────────────────────────────────────────────────────────

class TestNum:
    def test_int(self):
        assert FinnhubFeed._num(42) == 42

    def test_none(self):
        assert FinnhubFeed._num(None) is None
