"""Containment for the free-context fetchers (secure2 sweep).

One caller of these fetchers takes a URL straight from user input — the news feed
(`context.news_url`, reachable as a GET query parameter, i.e. triggerable by any page the
user visits) — and one takes the symbol from a path/query parameter that is pasted into the
venue's URL template. Two containments are pinned here:

* `_fetch_text` fetches http(s) only. `file://` used to be read by `urlopen()` and handed to
  the RSS parser as if it were a feed (local files as "headlines"), and redirects could not
  leave http(s) either.
* the body is read through a hard byte ceiling, so a hostile or broken endpoint cannot stream
  unbounded bytes into the worker thread's memory.

Plus: `_venue_symbol` quotes the symbol, so a symbol can never add or change a query
parameter of the venue URL it lands in — the same treatment Deribit's currency now gets.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _serve_once(body: bytes):
    """A one-shot loopback HTTP server; returns (url, server)."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib naming
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # keep pytest output clean
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}/feed", server


def test_a_non_http_scheme_is_refused_before_any_read():
    """`file://` and friends must be refused: this fetcher is reachable with a user URL."""
    from orderflow_system.atlas import context as ctx

    for bad in ("file:///C:/Windows/win.ini", "ftp://example.invalid/feed",
                "data:text/plain,hello"):
        try:
            ctx._fetch_text(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad} was fetched — only http(s) may be")


def test_a_normal_response_is_read_whole_and_an_oversized_one_is_refused():
    from orderflow_system.atlas import context as ctx

    body = b"<rss>" + b"x" * (300 * 1024) + b"</rss>"
    url, server = _serve_once(body)
    try:
        assert ctx._fetch_text(url, timeout_s=5.0).endswith("</rss>"), "normal reads untouched"
        try:
            ctx._fetch_text(url, timeout_s=5.0, max_bytes=1024)
        except ValueError as exc:
            assert "exceed" in str(exc)
        else:
            raise AssertionError("an oversized body was accepted — the cap is not enforced")
    finally:
        server.shutdown()
        server.server_close()


def test_a_symbol_cannot_add_or_change_query_parameters():
    from orderflow_system.atlas import context as ctx

    assert ctx._venue_symbol("BTCUSDT") == "BTCUSDT"          # the normal shape is unchanged
    assert ctx._venue_symbol("btcusdt") == "BTCUSDT"
    hostile = ctx._venue_symbol("BTC&limit=1/../x?y=z")
    for ch in "&=?/ ":
        assert ch not in hostile, f"{ch!r} survived quoting: {hostile}"


def test_the_bybit_templates_use_the_quoted_symbol():
    from orderflow_system.atlas import context as ctx

    url = ctx._BYBIT_TICKERS.format(symbol=ctx._venue_symbol("BTC&evil=1"))
    assert url.count("&") == 1, url            # only the template's own separator survives
    assert "evil" not in url, url


def test_a_feed_with_an_internal_dtd_subset_is_refused_but_normal_feeds_parse():
    """Entity-trick XML is dropped before the parser; ordinary feeds keep parsing."""
    from orderflow_system.atlas.context import parse_rss

    evil = ('<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY a "AAAA">]>'
            '<rss><channel><item><title>&a;&a;&a;</title>'
            '<link>http://example.invalid/</link></item></channel></rss>')
    assert parse_rss(evil) == [], "an internal DTD subset must not reach the parser"

    # a plain (external) DOCTYPE is not an attack carrier and must stay accepted
    with_doctype = ('<?xml version="1.0"?><!DOCTYPE rss SYSTEM "http://example.invalid/rss.dtd">'
                    '<rss><channel><item><title>ok</title>'
                    '<link>https://example.com/a</link></item></channel></rss>')
    assert [i["title"] for i in parse_rss(with_doctype)] == ["ok"]

    # and an ordinary feed is untouched
    plain = ('<rss><channel><item><title>hello</title>'
             '<link>https://example.com/a</link></item></channel></rss>')
    items = parse_rss(plain)
    assert items and items[0]["title"] == "hello"


def test_the_deribit_currency_is_quoted_too():
    """Same class, second venue: the chain's currency must not inject query parameters."""
    from orderflow_system.desktop import deribit as dl

    seen: list[str] = []
    original = dl.get_json

    def capture(url, timeout=dl.TIMEOUT_S):
        seen.append(url)
        return None, "capped for the test"

    dl.get_json = capture
    try:
        dl.instruments("BTC&count=999")
    finally:
        dl.get_json = original
    assert seen, "instruments() did not call the venue"
    assert "&count=999" not in seen[0] and "%26" in seen[0], seen[0]
