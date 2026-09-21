"""The crypto-derivatives context (atlas/derivatives.py + desktop/ui/derivatives.js).

The claim this gate is about: for one instrument, the panel shows what the four public venues really
publish about carry and positioning — funding per settlement and annualised, open interest in the
venue's own unit plus USD, and the perp's basis against its index — or it says, in one plain sentence
naming the venue, why that venue has nothing to say. No number here is ever invented: an open-interest
change is measured against this app's own stored samples (and the read names the window it really
watched), a venue that does not publish a figure contributes no figure, and a venue that rate-limits,
404s or serves something that is not JSON becomes a sentence rather than an exception.

What is pinned here, against small captures taken from the real endpoints (the payload shapes below
were read off the venues live before the parsers were written):

* the settings block: ``clean()`` coercion/clamping, the venue list that survives, and the names it
  refuses to invent a venue for;
* the arithmetic: annualising a rate through its own settlement interval, the mark-vs-index basis in
  bps and its annualised shorthand, and the open-interest change over a window with its minimum-span
  rule and its "which window did I really watch" answer;
* the four parsers, each against its venue's captured shape — including the venues' own error
  envelopes (Bybit ``retCode``, OKX ``code``, Binance's ``msg``) and payloads that are not what we
  expect at all;
* the assembled payload: the per-venue rows, the cross-venue funding read with its crowds, the OI
  read, the basis read, and the one plain sentence at and around every threshold that changes it;
* the same sentence in JavaScript, run in Node over the same numbers, compared string for string, so
  the two implementations of one wording cannot drift;
* the refusals: a raising fetch names each venue and its reason, no venue answering is one joined
  sentence under ``detail``, an unknown venue name is refused by name, and no route ever 500s;
* the route surface: declared on this module's own router, discoverable by scripts/audit_ui_refs.py's
  own scanner, one round of venue calls per refresh window, and read-only apart from the venue POST.

Everything runs offline: the network is one injected ``fetch`` callable, exactly as
``DerivativesService(fetch=...)`` documents.

Run:  .venv/Scripts/python.exe -m pytest orderflow_system/test_derivatives.py -q
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import re
import shutil
import subprocess
import urllib.error
from pathlib import Path

import pytest

from orderflow_system.atlas import derivatives

ROOT = Path(__file__).resolve().parents[1]
PKG = Path(__file__).parent
UI = PKG / "desktop" / "ui"
PANEL = UI / "derivatives.js"
SELFTEST = UI / "derivatives.selftest.js"
MODULE = PKG / "atlas" / "derivatives.py"
AUDIT = ROOT / "scripts" / "audit_ui_refs.py"

#: The moment every capture was taken (ms) — when BTC was ~80.4k on all four venues at once.
NOW = 1_789_905_483_478

# ── captured payloads (trimmed to the fields the parsers read) ──────────────────────────────────────

BYBIT_TICKERS = {
    "retCode": 0, "retMsg": "OK", "time": 1789905483478,
    "result": {"category": "linear", "list": [{
        "symbol": "BTCUSDT", "lastPrice": "80417.90", "indexPrice": "80466.07", "markPrice": "80421.58",
        "openInterest": "55420.091", "openInterestValue": "4456971281.96", "fundingRate": "0.00006032",
        "nextFundingTime": "1789920000000", "fundingIntervalHour": "8", "fundingCap": "0.00333",
    }]},
}

BINANCE_PREMIUM = {
    "symbol": "BTCUSDT", "markPrice": "80425.55440580", "indexPrice": "80466.63086957",
    "estimatedSettlePrice": "80461.00406513", "lastFundingRate": "0.00010000",
    "interestRate": "0.00010000", "nextFundingTime": 1789920000000, "time": 1789905483000,
}

BINANCE_OI = {"symbol": "BTCUSDT", "openInterest": "108955.553", "time": 1789905479005}

OKX_FUNDING = {"code": "0", "msg": "", "data": [{
    "instId": "BTC-USDT-SWAP", "instType": "SWAP", "fundingRate": "0.0000988547834084",
    "fundingTime": "1789920000000", "nextFundingTime": "1789948800000", "prevFundingTime": "1789891200000",
    "method": "current_period", "maxFundingRate": "0.00375", "ts": "1789905422958",
}]}

OKX_OI = {"code": "0", "msg": "", "data": [{
    "instId": "BTC-USDT-SWAP", "oi": "3068823.42000001069", "oiCcy": "30688.2342000001069",
    "oiUsd": "2468196369.06102859776389", "ts": "1789905487206",
}]}

OKX_MARK = {"code": "0", "msg": "", "data": [{"instId": "BTC-USDT-SWAP", "markPx": "80426.8",
                                              "ts": "1789905487407"}]}

OKX_INDEX = {"code": "0", "msg": "", "data": [{"instId": "BTC-USDT", "idxPx": "80463",
                                               "ts": "1789905487047"}]}

HL_META_CONTEXTS = [
    {"universe": [{"name": "BTC", "szDecimals": 5}, {"name": "ETH", "szDecimals": 4},
                  {"name": "MATIC", "szDecimals": 1, "isDelisted": True}]},
    [{"funding": "0.0000125", "openInterest": "40478.48844", "prevDayPx": "81351.0",
      "dayNtlVlm": "1486786690.2000803947", "premium": "0.0000372828", "oraclePx": "80466.0",
      "markPx": "80469.0", "midPx": "80469.5", "impactPxs": ["80469.0", "80470.0"]},
     {"funding": "0.00001", "openInterest": "1234.5", "oraclePx": "3000.0", "markPx": "3001.0"},
     {"funding": "0.0", "openInterest": "0.0", "oraclePx": "0.4", "markPx": "0.4"}],
]

#: URL fragment → the venue's answer. Every fragment is a piece of a real endpoint this module
#: documents in its docstring, and the two open-interest fragments differ (Binance camel-cases it,
#: OKX hyphenates it) exactly as the venues do.
ALL_VENUES = {
    "bybit.com": BYBIT_TICKERS,
    "premiumIndex": BINANCE_PREMIUM,
    "fapi/v1/openInterest": BINANCE_OI,
    "funding-rate": OKX_FUNDING,
    "mark-price": OKX_MARK,
    "index-tickers": OKX_INDEX,
    "public/open-interest": OKX_OI,
    "hyperliquid.xyz": HL_META_CONTEXTS,
}


class _Stub:
    """A fetch that answers from a table: URL fragment → payload, or an exception to raise.

    The first fragment that matches, in the order given. A URL nobody planned is an
    AssertionError, so a call can never quietly run against a payload the test did not intend —
    which is how a wrong endpoint would otherwise pass unnoticed.
    """

    def __init__(self, table: dict[str, object] | None = None, default: object = None) -> None:
        self.table = dict(table or {})
        self.default = default
        self.calls: list[str] = []

    def __call__(self, url: str):
        self.calls.append(str(url))
        for fragment, answer in self.table.items():
            if fragment in url:
                if isinstance(answer, BaseException):
                    raise answer
                return answer
        if isinstance(self.default, BaseException):
            raise self.default
        if self.default is not None:
            return self.default
        raise AssertionError("unexpected URL: " + url)

    @property
    def urls(self) -> list[str]:
        return list(self.calls)


def _service(stub, *, now: int = NOW, history=None) -> derivatives.DerivativesService:
    return derivatives.DerivativesService(fetch=stub, now_ms=lambda: now, history=history)


def _read(stub, symbol: str = "BTCUSDT", cfg=None, **kw) -> dict:
    return _service(stub, **kw).read(symbol, cfg)


def _clocked(stub, clock: dict, history=None):
    """A service whose 'now' the test advances between reads."""
    return derivatives.DerivativesService(fetch=stub, now_ms=lambda: clock["now"], history=history)


def _funding_rows(*specs) -> list[dict]:
    """Rows shaped like ``row_for()``'s output, for the fields ``funding_read`` actually reads.

    ``specs`` are ``(venue, annualised_pct, interval_h)``; the per-settlement rate is derived from
    them the way the parsers do, so a sentence quoted from the read is the sentence a user would see.
    """
    rows = []
    for venue, apr, hours in specs:
        rate = apr / (derivatives.ANNUAL_HOURS / hours) / 100.0
        rows.append({"venue": venue, "label": derivatives.label_of(venue), "funding_rate": rate,
                     "funding_pct": rate * 100.0, "funding_interval_h": hours,
                     "funding_apr_pct": apr})
    return rows


@pytest.fixture(autouse=True)
def _fresh_cache():
    """The route's read cache is module state; no test may inherit another one's answer."""
    derivatives._cache.clear()
    yield
    derivatives._cache.clear()


# ──────────────────────────────────────────────────────────────────────────────
# settings
# ──────────────────────────────────────────────────────────────────────────────

def test_clean_returns_the_defaults_for_junk():
    for junk in (None, "bybit", 7, [], {"venues": None, "refresh_s": object()}):
        assert derivatives.clean(junk) == derivatives.DEFAULTS
    # ...and the block it returns is a copy: a caller may edit it without editing the defaults.
    cleaned = derivatives.clean(None)
    cleaned["venues"].append("mt5")
    assert derivatives.DEFAULTS["venues"] == list(derivatives.VENUES)


def test_clean_keeps_unknown_keys_out():
    cleaned = derivatives.clean({"refresh_s": 30, "wat": True, "venues": ["bybit"]})
    assert set(cleaned) == set(derivatives.DEFAULTS)
    assert "wat" not in cleaned


def test_clean_coerces_types_and_clamps_values():
    cleaned = derivatives.clean({"refresh_s": "120", "oi_window_s": 10, "crowded_apr_pct": 5,
                                 "flat_apr_pct": "2.5", "history_max": 1})
    assert cleaned["refresh_s"] == 120                    # a numeric string is a number
    assert cleaned["oi_window_s"] == 300                  # 10 s is under the floor
    assert cleaned["crowded_apr_pct"] == 5.0              # a 5% crowd line is honoured, not clamped away
    assert cleaned["flat_apr_pct"] == 2.5
    assert cleaned["history_max"] == 60
    huge = derivatives.clean({"refresh_s": 99999, "oi_window_s": 10 ** 9, "crowded_apr_pct": 10 ** 9,
                              "history_max": 10 ** 9})
    assert (huge["refresh_s"], huge["oi_window_s"], huge["history_max"]) == (3600, 604800, 20000)
    assert huge["crowded_apr_pct"] == 1000.0


def test_a_flat_threshold_can_never_be_looser_than_a_crowded_one():
    cleaned = derivatives.clean({"crowded_apr_pct": 12, "flat_apr_pct": 40})
    assert cleaned["flat_apr_pct"] == 12.0


def test_the_venue_list_keeps_what_it_covers_and_cannot_end_up_empty():
    assert derivatives.clean({"venues": "bybit, Binance ,okx"})["venues"] == ["bybit", "binance", "okx"]
    assert derivatives.clean({"venues": ["BYBIT", "bybit"]})["venues"] == ["bybit"]
    # A list with nothing covered in it keeps the default four rather than blanking the panel...
    assert derivatives.clean({"venues": ["sonic", "tradingview"]})["venues"] == list(derivatives.VENUES)
    # ...and the names it could not honour are reported, never silently rewritten onto a real venue.
    kept, dropped = derivatives.accepted_venues("sonic, bybit, mt5")
    assert kept == ["bybit"] and dropped == ["sonic", "mt5"]
    assert derivatives.accepted_venues(None) == ([], [])
    assert derivatives.accepted_venues(["", "   "]) == ([], [])


# ──────────────────────────────────────────────────────────────────────────────
# the arithmetic
# ──────────────────────────────────────────────────────────────────────────────

def test_a_rate_annualises_through_its_own_settlement_interval():
    # The same 0.01% per settlement is 10.95%/yr every 8 h and 87.6%/yr every hour.
    assert derivatives.annualise_pct(0.0001, 8) == pytest.approx(10.95)
    assert derivatives.annualise_pct(0.0001, 1) == pytest.approx(87.6)
    assert derivatives.annualise_pct(0.0001, 4) == pytest.approx(21.9)
    assert derivatives.annualise_pct(0.0001, 0) is None            # no interval, no annualising
    assert derivatives.annualise_pct(None, 8) is None
    assert derivatives.annualise_pct("nan", 8) is None


def test_the_basis_is_mark_against_index_in_bps():
    # Hyperliquid's own `premium` field is (mark - oracle) / oracle: the arithmetic must agree with
    # the venue's own published figure rather than merely look plausible.
    assert derivatives.basis_bps(80469.0, 80466.0) == pytest.approx(0.372828, abs=1e-6)
    bybit = derivatives.basis_bps(80421.58, 80466.07)
    assert bybit == pytest.approx(-5.529, abs=0.001)
    assert derivatives.basis_bps(0.0, 80466.0) is None             # a missing mark is not -100%
    assert derivatives.basis_bps(80469.0, 0) is None
    assert derivatives.basis_bps(None, None) is None
    # annualised as if the premium held all year (bps → fraction → a year → percent): a shorthand,
    # printed with that caveat wherever it appears
    assert derivatives.basis_apr_pct(bybit) == pytest.approx(bybit / 10_000.0 * 365.0 * 100.0)
    assert derivatives.basis_apr_pct(bybit) == pytest.approx(-20.18, abs=0.01)
    assert derivatives.basis_apr_pct(None) is None


def test_the_open_interest_change_needs_a_baseline_and_a_span():
    day = 86_400_000
    assert derivatives.oi_change([], 86400, NOW)["pct"] is None
    assert derivatives.oi_change([], 86400, NOW)["reason"] == "no open-interest samples yet"
    assert derivatives.oi_change([(NOW - day, 100.0)], 86400, NOW)["reason"] == (
        "only one open-interest sample so far")
    # two samples a second apart: noise, refused rather than reported as a statistic
    short = derivatives.oi_change([(NOW - 1000, 100.0), (NOW - 900, 103.0)], 86400, NOW)
    assert short["pct"] is None and "only 0 s of samples" in short["reason"]
    # a real day of it
    change = derivatives.oi_change([(NOW - day, 100.0), (NOW - day // 2, 101.0), (NOW, 103.2)],
                                   86400, NOW)
    assert change["pct"] == pytest.approx(3.2)
    assert change["span_s"] == pytest.approx(86400.0)
    assert change["window_limited"] is False and change["samples"] == 3
    assert change["baseline_ms"] == NOW - day


def test_the_open_interest_change_never_claims_a_window_it_did_not_watch():
    partial = derivatives.oi_change([(NOW - 7200_000, 100.0), (NOW, 101.5)], 86400, NOW)
    assert partial["pct"] == pytest.approx(1.5)
    assert partial["window_limited"] is True                       # the baseline is the oldest sample
    assert partial["baseline_ms"] == NOW - 7200_000
    # a day was asked for and only two hours exist: the sentence names two hours, never "the day"
    assert derivatives.span_text(partial["span_s"], 86400) == "over the last 2 h"


def test_the_open_interest_change_ignores_samples_it_cannot_use():
    day = 86_400_000
    series = [(NOW - day, 100.0), (NOW - day // 2, 0.0), (NOW - 60_000, -5.0), (NOW, 103.2),
              (NOW + day, 999.0)]                                  # a future sample is not a baseline
    change = derivatives.oi_change(series, 86400, NOW)
    assert change["samples"] == 2 and change["pct"] == pytest.approx(3.2)
    # unsorted input is sorted, and the newest usable sample is the reading
    assert derivatives.oi_change([(NOW, 103.2), (NOW - day, 100.0)], 86400, NOW)["pct"] == (
        pytest.approx(3.2))


def test_the_minimum_span_scales_with_the_window_but_never_goes_below_a_minute():
    series = [(NOW - 30_000, 100.0), (NOW, 101.0)]
    assert derivatives.oi_change(series, 86400, NOW)["pct"] is None      # 30 s of a 24 h window
    assert derivatives.oi_change(series, 86400, NOW, min_span_s=10)["pct"] == pytest.approx(1.0)
    wide = [(NOW - 400_000, 100.0), (NOW, 110.0)]                        # 400 s of a 7-day window
    assert derivatives.oi_change(wide, 604800, NOW)["pct"] is None


# ──────────────────────────────────────────────────────────────────────────────
# the parsers, one venue's captured shape each
# ──────────────────────────────────────────────────────────────────────────────

def test_bybit_reads_the_captured_tickers_row():
    parsed = derivatives.parse_bybit({"tickers": BYBIT_TICKERS}, "BTCUSDT", now_ms=NOW)
    assert parsed["problem"] == ""
    fields = parsed["fields"]
    assert fields["funding_rate"] == pytest.approx(0.00006032)
    assert fields["funding_interval_h"] == 8.0                 # the venue names its own interval
    assert fields["next_funding_ms"] == 1789920000000
    assert fields["mark"] == pytest.approx(80421.58)
    assert fields["index"] == pytest.approx(80466.07)
    assert fields["open_interest"] == pytest.approx(55420.091)
    assert fields["open_interest_unit"] == "BTC"
    assert fields["open_interest_usd"] == pytest.approx(4456971281.96)   # the venue's own USD figure
    assert fields["ts_ms"] == 1789905483478


def test_bybit_refuses_its_own_error_code_and_an_empty_listing():
    refused = derivatives.parse_bybit({"tickers": {"retCode": 10001, "retMsg": "params error"}})
    assert "retCode 10001" in refused["problem"] and "params error" in refused["problem"]
    empty = derivatives.parse_bybit({"tickers": {"retCode": 0, "result": {"list": []}}}, "BTCUSDT")
    assert "did not carry BTCUSDT" in empty["problem"]
    assert derivatives.parse_bybit({})["problem"] == "the venue's ticker payload did not arrive"


def test_binance_merges_the_two_calls_it_needs():
    parsed = derivatives.parse_binance({"premium_index": BINANCE_PREMIUM, "open_interest": BINANCE_OI},
                                       "BTCUSDT", now_ms=NOW)
    assert parsed["problem"] == ""
    fields = parsed["fields"]
    assert fields["funding_rate"] == pytest.approx(0.0001)
    assert fields["funding_interval_h"] is None                # the payload really carries none
    assert fields["mark"] == pytest.approx(80425.55440580)
    assert fields["index"] == pytest.approx(80466.63086957)
    assert fields["open_interest"] == pytest.approx(108955.553)
    assert fields["open_interest_unit"] == "BTC"
    # this venue publishes no USD figure, so the row's USD value is the app's own arithmetic
    assert fields["open_interest_usd"] == pytest.approx(108955.553 * 80425.55440580, rel=1e-9)
    assert any("computed from this venue's own open interest and mark" in note for note in parsed["notes"])
    assert any("assumes its 8 h default" in note for note in parsed["notes"])


def test_binance_refuses_a_symbol_it_does_not_list():
    parsed = derivatives.parse_binance({"premium_index": {"code": -1121, "msg": "Invalid symbol."}})
    assert parsed["problem"] == "Invalid symbol."
    assert derivatives.parse_binance({})["problem"] == "the venue's premium-index payload did not arrive"


def test_okx_reads_the_envelopes_that_were_captured():
    parsed = derivatives.parse_okx({"funding_rate": OKX_FUNDING, "mark_price": OKX_MARK,
                                    "index_tickers": OKX_INDEX, "open_interest": OKX_OI},
                                   "BTC-USDT-SWAP", now_ms=NOW)
    assert parsed["problem"] == ""
    fields = parsed["fields"]
    assert fields["funding_rate"] == pytest.approx(0.0000988547834084)
    # the funding times carry the settlement spacing: `nextFundingTime - fundingTime` is 8 h here
    assert fields["funding_interval_h"] == 8.0
    assert any("spacing was read from the venue's own funding times" in note for note in parsed["notes"])
    # `fundingTime` is ahead of the capture, so it is the next settlement (not the one after it)
    assert fields["next_funding_ms"] == 1789920000000
    assert fields["mark"] == pytest.approx(80426.8)
    assert fields["index"] == pytest.approx(80463)
    # oiCcy is the coin figure; the venue's raw contract count is a different unit and is not used
    assert fields["open_interest"] == pytest.approx(30688.2342000001069)
    assert fields["open_interest"] != pytest.approx(3068823.42)
    assert fields["open_interest_usd"] == pytest.approx(2468196369.06)


def test_a_contract_count_is_never_published_as_a_coin_figure():
    """T5-F03 (§148): with OKX's `oiCcy` absent the row fell back to the raw contract count (`oi`) and
    published it under a coin label — a different unit wearing the coin's name, ~100x off. Now the
    fallback is gone: no coin figure means no coin figure, and the row says why."""
    payload = json.loads(json.dumps(OKX_OI))
    payload["data"][0].pop("oiCcy")
    parsed = derivatives.parse_okx({"funding_rate": OKX_FUNDING, "mark_price": OKX_MARK,
                                    "index_tickers": OKX_INDEX, "open_interest": payload},
                                   "BTC-USDT-SWAP", now_ms=NOW)
    fields = parsed["fields"]
    assert fields["open_interest"] is None, \
        "the contract count must never stand in for the coin figure"
    assert fields["open_interest_unit"] == "", "and no unit is claimed for a figure that is not there"
    assert any("only a contract count" in note for note in parsed["notes"])
    assert not any("did not arrive" in note for note in parsed["notes"]), \
        "the payload arrived — that note would be a second, false story"
    # The USD figure the venue published itself is untouched by any of this.
    payload_usd = json.loads(json.dumps(OKX_OI))
    payload_usd["data"][0].pop("oiCcy")
    parsed_usd = derivatives.parse_okx({"funding_rate": OKX_FUNDING, "mark_price": OKX_MARK,
                                        "index_tickers": OKX_INDEX, "open_interest": payload_usd},
                                       "BTC-USDT-SWAP", now_ms=NOW)
    assert parsed_usd["fields"]["open_interest_usd"] == pytest.approx(2468196369.06)


def test_okx_uses_the_name_the_venue_gave_its_interval():
    payload = json.loads(json.dumps(OKX_FUNDING))
    payload["data"][0].pop("prevFundingTime")
    payload["data"][0].pop("nextFundingTime")
    payload["data"][0]["fundingIntervalHours"] = "4"
    parsed = derivatives.parse_okx({"funding_rate": payload}, "BTC-USDT-SWAP", now_ms=NOW)
    assert parsed["fields"]["funding_interval_h"] == 4.0


def test_okx_moves_on_to_the_next_window_when_the_payload_is_stale():
    # A capture taken AFTER fundingTime: the row must show the following settlement, not a past one.
    stale = derivatives.parse_okx({"funding_rate": OKX_FUNDING}, "BTC-USDT-SWAP",
                                  now_ms=1789920000000 + 1000)
    assert stale["fields"]["next_funding_ms"] == 1789948800000
    # ...and a payload with no funding time at all still parses, with no countdown invented
    bare = derivatives.parse_okx({"funding_rate": {"code": "0", "data": [{"fundingRate": "0.0001"}]}},
                                 "BTC-USDT-SWAP", now_ms=NOW)
    assert bare["problem"] == "" and bare["fields"]["next_funding_ms"] is None
    assert bare["fields"]["funding_interval_h"] is None


def test_okx_refuses_the_venues_own_error_envelope():
    parsed = derivatives.parse_okx({"funding_rate": {"code": "51001", "msg": "Instrument ID does not exist",
                                                    "data": []}})
    assert parsed["problem"] == "OKX answered code 51001: Instrument ID does not exist"
    assert derivatives.parse_okx({})["problem"] == "the venue's funding payload did not arrive"
    assert derivatives.parse_okx({"funding_rate": {"code": "0", "data": []}})["problem"] == (
        "OKX returned no funding row for this instrument")


def test_hyperliquid_is_read_by_the_listing_order():
    parsed = derivatives.parse_hyperliquid({"meta_contexts": HL_META_CONTEXTS}, "BTC", now_ms=NOW)
    assert parsed["problem"] == ""
    fields = parsed["fields"]
    assert fields["funding_rate"] == pytest.approx(0.0000125)   # the venue's rate is per HOUR
    assert fields["funding_interval_h"] is None                 # ...and the 1 h default fills it in
    assert fields["mark"] == pytest.approx(80469.0)
    assert fields["index"] == pytest.approx(80466.0)            # oraclePx is the index
    assert fields["open_interest"] == pytest.approx(40478.48844)
    assert fields["open_interest_usd"] == pytest.approx(40478.48844 * 80469.0, rel=1e-9)
    # no timestamp in the document: the row's age stays unknown rather than being stamped with ours
    assert fields["ts_ms"] is None
    assert any("settles funding hourly" in note for note in parsed["notes"])
    assert any("no timestamp" in note for note in parsed["notes"])
    # the second coin in the listing is not this instrument
    eth = derivatives.parse_hyperliquid({"meta_contexts": HL_META_CONTEXTS}, "ETH")
    assert eth["fields"]["open_interest"] == pytest.approx(1234.5)


def test_hyperliquid_refuses_a_coin_its_listing_does_not_carry():
    parsed = derivatives.parse_hyperliquid({"meta_contexts": HL_META_CONTEXTS}, "SOL")
    assert parsed["problem"] == "Hyperliquid's listing did not carry SOL"
    assert derivatives.parse_hyperliquid({"meta_contexts": []})["problem"] == (
        "the venue's meta-and-contexts payload did not arrive")


def test_every_parser_survives_a_payload_that_is_not_what_we_expect():
    """A venue that changes shape or serves an error page must produce a sentence, not a traceback."""
    junk = [None, {}, [], {"unexpected": True}, [1, 2, 3], "not json", 5]
    for venue, parser in derivatives.PARSERS.items():
        for payload in junk:
            parsed = parser({"tickers": payload, "premium_index": payload, "funding_rate": payload,
                             "meta_contexts": payload, "open_interest": payload}, "BTCUSDT")
            assert isinstance(parsed["problem"], str) and parsed["problem"], (venue, payload)
            assert parsed["fields"]["funding_rate"] is None
    # ...and a payload with the right names but unreadable values reads as no value, not as zero
    parsed = derivatives.parse_bybit({"tickers": {"retCode": 0, "result": {"list": [
        {"fundingRate": "abc", "markPrice": None, "openInterest": "nan", "nextFundingTime": "soon"}]}}},
        "BTCUSDT")
    assert parsed["problem"] == ""
    assert parsed["fields"]["funding_rate"] is None
    assert parsed["fields"]["mark"] is None
    assert parsed["fields"]["open_interest"] is None
    assert parsed["fields"]["next_funding_ms"] is None


# ──────────────────────────────────────────────────────────────────────────────
# symbols and endpoints
# ──────────────────────────────────────────────────────────────────────────────

def test_each_venue_is_asked_in_its_own_symbol():
    assert derivatives.venue_instrument("bybit", " btcusdt ") == "BTCUSDT"
    assert derivatives.venue_instrument("binance", "BTCUSDT") == "BTCUSDT"
    assert derivatives.venue_instrument("okx", "BTCUSDT") == "BTC-USDT-SWAP"
    assert derivatives.venue_instrument("okx", "BTC-USDT-SWAP") == "BTC-USDT-SWAP"   # already venue form
    assert derivatives.venue_instrument("hyperliquid", "BTCUSDT") == "BTC"
    assert derivatives.base_coin("BTC-USDT-SWAP") == "BTC"
    assert derivatives.base_coin("KPEPEUSDT") == "KPEPE"
    assert derivatives.base_coin("") == ""
    assert derivatives.normalise_symbol(" btcusdt ") == "BTCUSDT"
    assert derivatives.normalise_symbol(None) == ""


def test_every_venue_is_read_through_public_routes_only():
    for venue in derivatives.VENUES:
        urls = [url for _name, url, _required in derivatives.venue_calls(venue, "BTCUSDT")]
        assert urls, venue
        for url in urls:
            assert url.startswith("https://"), url
            assert "api_key" not in url and "token" not in url and "secret" not in url
    assert derivatives.venue_calls("mt5", "BTCUSDT") == ()
    okx = derivatives.venue_calls("okx", "BTCUSDT")
    assert [name for name, _url, _req in okx] == ["funding_rate", "mark_price", "index_tickers",
                                                 "open_interest"]
    assert "instId=BTC-USDT-SWAP" in okx[0][1]
    assert "instId=BTC-USDT" in okx[2][1]                       # the index instrument, not the swap
    required = [name for name, _url, req in derivatives.venue_calls("binance", "BTCUSDT") if req]
    assert required == ["premium_index"], "open interest is optional: its loss must not blank the row"
    hl = derivatives.venue_calls("hyperliquid", "BTCUSDT")
    assert hl[0][1] == f"{derivatives.HYPERLIQUID_REST}/info?type=metaAndAssetCtxs"


# ──────────────────────────────────────────────────────────────────────────────
# refusals
# ──────────────────────────────────────────────────────────────────────────────

def test_a_venue_that_does_not_answer_is_named_with_a_plain_reason():
    cases = [
        (urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None), "rate-limiting"),
        (urllib.error.HTTPError("u", 451, "Unavailable", {}, None), "refused the request"),
        (urllib.error.HTTPError("u", 500, "Server Error", {}, None), "HTTP 500"),
        (urllib.error.URLError("getaddrinfo failed"), "could not be reached"),
        (TimeoutError("timed out"), "timed out"),
        (json.JSONDecodeError("x", "<html>", 0), "not JSON"),
        (OSError("connection reset by peer"), "connection failed"),
    ]
    for exc, expected in cases:
        reason = derivatives.reason_of(exc)
        assert expected in reason, (exc, reason)
        assert "Traceback" not in reason and "Error:" not in reason
        sentence = derivatives.unreachable_sentence("bybit", exc)
        assert sentence.startswith("Bybit did not answer — "), sentence


def test_a_venue_that_raises_becomes_a_row_and_never_an_exception():
    stub = _Stub({"bybit.com": urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)})
    observed = derivatives.read_venue("bybit", "BTCUSDT", stub, now_ms=NOW)
    assert observed["ok"] is False
    assert observed["reason"] == "the venue is rate-limiting this machine (HTTP 429)"
    assert observed["problem"].startswith("Bybit did not answer — ")
    assert observed["fields"] == {}
    assert stub.urls and "api.bybit.com" in stub.urls[0]


def test_a_venue_this_panel_does_not_cover_is_refused_by_name():
    observed = derivatives.read_venue("sonic", "BTCUSDT", _Stub(ALL_VENUES), now_ms=NOW)
    assert observed["ok"] is False
    assert observed["problem"].startswith("Sonic is not a venue this panel covers")
    assert "Bybit, Binance, OKX, Hyperliquid" in observed["problem"]
    assert derivatives.label_of("vipBOT") == "Vipbot"           # an unknown name is still a name
    assert derivatives.unsupported_sentence("").startswith("That name is not a venue this panel covers")


def test_a_secondary_call_that_fails_leaves_a_note_not_a_blank_row():
    stub = _Stub({"premiumIndex": BINANCE_PREMIUM, "fapi/v1/openInterest": OSError("connection reset")})
    observed = derivatives.read_venue("binance", "BTCUSDT", stub, now_ms=NOW)
    assert observed["ok"] is True
    assert observed["fields"]["funding_rate"] == pytest.approx(0.0001)
    assert observed["fields"]["open_interest"] is None
    assert any("open interest call did not answer" in note for note in observed["notes"])


def test_no_venue_answering_is_one_joined_sentence():
    payload = _read(_Stub(default=OSError("connection reset by peer")))
    assert payload["ok"] is False
    assert payload["detail"] == payload["error"]                # both keys, one sentence
    assert payload["detail"].startswith("no venue answered for BTCUSDT — ")
    for label in ("Bybit", "Binance", "OKX", "Hyperliquid"):
        assert f"{label}: the connection failed (connection reset by peer)" in payload["detail"]
    assert "Traceback" not in json.dumps(payload)
    assert payload["summary"] == ""
    # the table is still there: a reader sees which venue said what, each with its own sentence
    assert [row["venue"] for row in payload["venues"]] == ["bybit", "binance", "okx", "hyperliquid"]
    assert all(row["ok"] is False and row["reason"] and row["error"] for row in payload["venues"])
    assert payload["funding"]["available"] is False and payload["oi"]["available"] is False


# ──────────────────────────────────────────────────────────────────────────────
# the assembled payload
# ──────────────────────────────────────────────────────────────────────────────

def test_the_read_builds_one_row_per_venue_from_the_captured_shapes():
    payload = _read(_Stub(ALL_VENUES))
    assert payload["ok"] is True
    assert payload["symbol"] == "BTCUSDT"
    assert payload["venues_asked"] == 4 and payload["venues_ok"] == 4
    assert [row["venue"] for row in payload["venues"]] == ["bybit", "binance", "okx", "hyperliquid"]
    rows = {row["venue"]: row for row in payload["venues"]}
    assert rows["bybit"]["funding_apr_pct"] == pytest.approx(6.605, abs=0.001)
    assert rows["binance"]["funding_apr_pct"] == pytest.approx(10.95, abs=0.001)
    assert rows["okx"]["funding_apr_pct"] == pytest.approx(10.8246, abs=0.001)
    # Hyperliquid settles hourly, so its rate annualises through the hourly interval
    assert rows["hyperliquid"]["funding_interval_h"] == 1.0
    assert rows["hyperliquid"]["funding_apr_pct"] == pytest.approx(10.95, abs=0.001)
    assert rows["hyperliquid"]["next_funding_in_s"] is None      # nothing to count down to
    assert rows["bybit"]["next_funding_in_s"] == pytest.approx(14516.5, abs=1.0)
    assert rows["bybit"]["open_interest_unit"] == "BTC"
    assert rows["okx"]["open_interest"] == pytest.approx(30688.2342, abs=0.001)
    assert rows["hyperliquid"]["age_ms"] is None                 # no timestamp, no invented age
    assert rows["bybit"]["age_ms"] == 0                          # the venue's own stamp


def test_the_cross_venue_reads_are_medians_and_totals_not_the_first_row():
    service = _service(_Stub(ALL_VENUES))
    payload = service.read("BTCUSDT")
    funding = payload["funding"]
    assert funding["available"] is True
    assert funding["median_apr_pct"] == pytest.approx(10.8873, abs=0.001)
    assert funding["min_apr_pct"] == pytest.approx(6.605, abs=0.001)
    assert funding["max_apr_pct"] == pytest.approx(10.95, abs=0.001)
    assert funding["spread_apr_pct"] == pytest.approx(4.345, abs=0.001)
    assert funding["direction"] == "longs_pay" and funding["verdict"] == "longs pay"
    assert funding["crowded"] == []                             # 11%/yr is ordinary, not crowded
    # the rate the sentence quotes belongs to a real venue whose annualised figure is the median
    assert funding["median_interval_h"] == 8.0
    assert funding["median_rate"] == pytest.approx(0.0001)
    basis = payload["basis"]
    assert basis["available"] is True
    assert basis["median_bps"] == pytest.approx(-4.8019, abs=0.01)
    assert basis["min_bps"] == pytest.approx(-5.529, abs=0.01)
    assert basis["max_bps"] == pytest.approx(0.3728, abs=0.01)
    assert "not a yield" in basis["note"]
    oi = payload["oi"]
    assert oi["available"] is True
    assert oi["venues_usd"] == 4
    assert oi["total_usd"] == pytest.approx(4456971281.96 + 108955.553 * 80425.55440580
                                            + 2468196369.06 + 40478.48844 * 80469.0, rel=1e-6)
    assert oi["unit"] == "BTC"
    assert oi["change_pct"] is None and oi["reason"] == "only one open-interest sample so far"
    # the sample kept for the next read is the sum this read published — not one venue's share of
    # it, which would report a change belonging to a different number altogether
    stored = service.history.series(derivatives.TOTAL_KEY, "BTCUSDT")
    assert len(stored) == 1 and stored[0][1] == pytest.approx(oi["total_usd"])


def test_the_summary_says_what_the_numbers_say():
    payload = _read(_Stub(ALL_VENUES))
    assert payload["summary"] == ("funding is +0.010%/8h (+10.9% annualised) with the open-interest "
                                  "change not known yet (only one open-interest sample so far) — "
                                  "longs are paying to hold")


def test_the_summary_claims_the_window_the_app_actually_watched():
    """An OI change is measured against this app's own samples, and the sentence names that window."""
    baseline = 18_000_000_000.0
    service = _service(_Stub(ALL_VENUES))
    service.history.add(derivatives.TOTAL_KEY, "BTCUSDT", NOW - 86_400_000, baseline)
    service.history.add("bybit", "BTCUSDT", NOW - 86_400_000, 53_000.0)
    payload = service.read("BTCUSDT")
    expected = (payload["oi"]["total_usd"] - baseline) / baseline * 100.0
    assert payload["oi"]["change_pct"] == pytest.approx(expected, abs=1e-3)   # published at 4 decimals
    assert f"with OI up {expected:.1f}% on the day" in payload["summary"], payload["summary"]
    assert payload["oi"]["span_s"] == pytest.approx(86_400.0, abs=1.0)
    assert payload["oi"]["window_limited"] is False
    assert payload["venues"][0]["oi_change_pct"] == pytest.approx(4.57, abs=0.05)   # 55420 / 53000

    two_hours = _service(_Stub(ALL_VENUES))
    two_hours.history.add(derivatives.TOTAL_KEY, "BTCUSDT", NOW - 7200_000, 15_000_000_000.0)
    partial = two_hours.read("BTCUSDT")
    soon = (partial["oi"]["total_usd"] - 15_000_000_000.0) / 15_000_000_000.0 * 100.0
    assert f"with OI up {soon:.1f}% over the last 2 h" in partial["summary"], partial["summary"]
    assert "on the day" not in partial["summary"]
    assert partial["oi"]["window_limited"] is True


def test_a_crowded_side_is_named_and_an_ordinary_one_is_not():
    cfg = derivatives.clean(None)                                # crowded past 30%/yr
    crowded = derivatives.funding_read(_funding_rows(("bybit", 43.8, 8.0)), cfg)
    assert crowded["verdict"] == "crowded long" and crowded["crowded_long"] is True
    assert [c["venue"] for c in crowded["crowded"]] == ["bybit"]
    assert derivatives.summary_line(crowded, {"change_pct": 3.2, "span_s": 86400, "window_s": 86400},
                                    cfg) == (
        "funding is +0.040%/8h (+43.8% annualised) with OI up 3.2% on the day — a crowded long: "
        "longs are paying to hold")
    # the threshold is the user's, not a constant: at 60% the same read is ordinary
    relaxed = derivatives.funding_read(_funding_rows(("bybit", 43.8, 8.0)),
                                       derivatives.clean({"crowded_apr_pct": 60}))
    assert relaxed["verdict"] == "longs pay" and relaxed["crowded"] == []
    # two venues past the line: the crowded list names both
    both = derivatives.funding_read(_funding_rows(("bybit", 43.8, 8.0), ("binance", 44.0, 8.0)), cfg)
    assert [c["venue"] for c in both["crowded"]] == ["bybit", "binance"]
    assert both["verdict"] == "crowded long"
    # a short crowd is named as one
    shorts = derivatives.funding_read(_funding_rows(("okx", -55.0, 4.0)), cfg)
    assert shorts["verdict"] == "crowded short" and shorts["crowded_short"] is True
    assert "a crowded short: shorts are paying to hold" in derivatives.summary_line(shorts, {}, cfg)


def test_the_crowded_and_flat_thresholds_sit_where_they_say_they_do():
    cfg = derivatives.clean(None)                                # crowded 30, flat 5
    assert derivatives.funding_read(_funding_rows(("bybit", 30.0, 8.0)), cfg)["verdict"] == "crowded long"
    assert derivatives.funding_read(_funding_rows(("bybit", 29.99, 8.0)), cfg)["verdict"] == "longs pay"
    assert derivatives.funding_read(_funding_rows(("bybit", 5.0, 8.0)), cfg)["verdict"] == "longs pay"
    under = derivatives.funding_read(_funding_rows(("bybit", 4.99, 8.0)), cfg)
    assert under["verdict"] == "flat"
    assert derivatives.summary_line(under, {}, cfg).endswith(
        "neither side is paying much (under 5% annualised)")


def test_venues_that_disagree_about_the_side_say_so():
    cfg = derivatives.clean(None)
    mixed = derivatives.funding_read(_funding_rows(("bybit", 45.0, 8.0), ("okx", -45.0, 8.0)), cfg)
    assert mixed["direction"] == "mixed" and mixed["verdict"] == "venues disagree"
    assert mixed["median_apr_pct"] == pytest.approx(0.0)
    assert "the venues disagree about which side is paying" in derivatives.summary_line(mixed, {}, cfg)
    # a tiny disagreement is a flat market, not a venues-at-war story
    small = derivatives.funding_read(_funding_rows(("bybit", 1.0, 8.0), ("okx", -1.0, 8.0)), cfg)
    assert small["direction"] == "flat"


def test_a_negative_rate_reads_as_the_shorts_being_paid():
    funding = derivatives.funding_read(_funding_rows(("bybit", -10.95, 8.0)), derivatives.clean(None))
    assert funding["direction"] == "shorts_pay"
    text = derivatives.funding_text(funding)
    assert text.startswith("-0.010%/8h (-10.9% annualised)"), text
    assert derivatives.funding_text({"available": True, "median_pct": 0.0, "median_interval_h": 8,
                                     "rate_apr_pct": 0.0}) == "0.000%/8h (0.0% annualised)"
    assert derivatives.funding_text({"available": False}) == "funding is not known"


def test_the_funding_sentence_annualises_the_rate_it_quotes():
    """T5-F01 (§148): with an even venue count the median annualised is the mean of the two middle
    venues, not the quoted venue's own figure — live, the sentence read "+0.010%/8h (+9.9%
    annualised)" where 0.010%/8h annualises to 10.95%. The parenthetical now comes from the quoted
    venue's own annualised figure, so the sentence's two numbers imply each other; the cross-venue
    median stays in its own field, untouched."""
    cfg = derivatives.clean(None)
    rows = _funding_rows(("bybit", 10.95, 8.0), ("binance", 4.5048, 8.0),
                         ("okx", 8.7869, 8.0), ("hyperliquid", 10.95, 1.0))
    funding = derivatives.funding_read(rows, cfg)
    assert funding["median_apr_pct"] == pytest.approx(9.86845, abs=1e-4), \
        "the cross-venue median is unchanged and still its own field"
    quoted = [v for v in funding["per_venue"] if abs(v["pct"] - funding["median_pct"]) < 1e-12]
    assert len(quoted) == 1, "the quoted rate is a real venue's, findable in per_venue"
    assert funding["rate_apr_pct"] == pytest.approx(quoted[0]["apr_pct"])
    implied = funding["median_pct"] * (24.0 / funding["median_interval_h"]) * 365
    assert funding["rate_apr_pct"] == pytest.approx(implied, rel=1e-9), \
        f"the quoted rate implies its own annualised figure ({funding['median_pct']}%/h -> {implied})"
    assert abs(funding["rate_apr_pct"] - funding["median_apr_pct"]) > 1.0, \
        "the fixture really is a mix when the median is used — otherwise this pin cannot bite"
    text = derivatives.funding_text(funding)
    assert text == "+0.010%/8h (+10.9% annualised)", text
    assert "+9.9%" not in text, "the cross-venue median never rides in the rate's parenthetical"


def test_the_oi_fallback_says_where_its_number_came_from():
    """T5-F02 (§148): when the venue-median fallback supplied the change, the payload still carried
    the total series' window metadata, so the sentence read "OI up 3.2% over the last 0 s" — a span
    this app never measured. Now an unknown span yields no span claim at all and the number's own
    source is named instead."""
    cfg = derivatives.clean(None)
    rows = [{"venue": "bybit", "oi_change_pct": 3.2, "open_interest_usd": 100.0},
            {"venue": "okx", "oi_change_pct": 5.0, "open_interest_usd": 50.0}]
    read = derivatives.oi_read(rows, cfg, 1_770_000_000_000, total_series=())
    assert read["change_pct"] == pytest.approx(4.1), "the fallback number is the venue median"
    assert read["span_s"] is None, "and it has no span of this app's own"
    text = derivatives.oi_text(read)
    assert text == "OI up 4.1% (the median of the venues that had a baseline)", text
    assert "0 s" not in text, "the phantom span is gone"
    # A measured span still reads as the span it is.
    assert derivatives.span_text(3600.0, 86400) == "over the last 1 h"
    assert derivatives.span_text(None, 86400) == ""
    # And with no venue that had a baseline either, the reason keeps its own sentence.
    bare = [{"venue": "bybit", "oi_change_pct": None, "open_interest_usd": 100.0}]
    unknown = derivatives.oi_read(bare, cfg, 1_770_000_000_000, total_series=((1_769_999_000_000, 1.0),))
    assert unknown["change_pct"] is None
    assert derivatives.oi_text(unknown).startswith("the open-interest change not known yet")


def test_the_strip_and_the_rows_are_the_same_numbers_the_aggregate_used():
    """Every figure a sentence quotes must be traceable to a row in the same payload."""
    payload = _read(_Stub(ALL_VENUES))
    rows = {row["venue"]: row for row in payload["venues"]}
    quoted = payload["funding"]["per_venue"]
    assert {item["apr_pct"] for item in quoted} == {rows[item["venue"]]["funding_apr_pct"]
                                                    for item in quoted}
    assert payload["oi"]["per_venue"] == {venue: row["oi_change_pct"] for venue, row in rows.items()
                                          if row["oi_change_pct"] is not None}


def test_a_venue_that_did_not_answer_is_still_in_the_table_with_its_sentence():
    table = dict(ALL_VENUES)
    table["hyperliquid.xyz"] = urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)
    payload = _read(_Stub(table))
    assert payload["ok"] is True and payload["venues_ok"] == 3
    hl = payload["venues"][3]
    assert hl["ok"] is False and hl["error"].startswith("Hyperliquid did not answer")
    assert hl["funding_rate"] is None and hl["basis_bps"] is None and hl["open_interest"] is None
    assert payload["errors"] == [{"venue": "hyperliquid", "label": "Hyperliquid",
                                  "reason": "the venue is rate-limiting this machine (HTTP 429)"}]
    # three venues still answer the sentence, and the median of three is the middle of the three
    assert payload["summary"].startswith("funding is ")
    assert payload["funding"]["median_apr_pct"] == pytest.approx(10.8246, abs=0.001)


def test_a_payload_that_is_not_json_is_a_sentence_not_a_crash():
    table = dict(ALL_VENUES)
    # OKX's required call is the funding one, so that is the fragment to poison — a key appended at
    # the end of the table would be shadowed by the earlier fragment it is meant to replace.
    table["funding-rate"] = ValueError("Expecting value: line 1 column 1 (char 0)")
    payload = _read(_Stub(table))
    assert payload["ok"] is True and payload["venues_ok"] == 3
    okx = {row["venue"]: row for row in payload["venues"]}["okx"]
    assert okx["reason"] == "the venue sent a reply that is not JSON"
    assert "Expecting value" not in okx["error"], "the parser's own words never reach the panel"


def test_an_instrument_only_one_venue_lists_still_answers():
    table = {"premiumIndex": urllib.error.HTTPError("u", 404, "Not Found", {}, None),
             "bybit.com": BYBIT_TICKERS,
             "hyperliquid.xyz": ValueError("not json"),
             "funding-rate": OKX_FUNDING, "mark-price": OKX_MARK, "index-tickers": OKX_INDEX,
             "public/open-interest": OKX_OI}
    payload = _read(_Stub(table))
    assert payload["ok"] is True and payload["venues_ok"] == 2
    assert payload["venues"][0]["venue"] == "bybit" and payload["venues"][0]["ok"] is True
    assert {row["venue"] for row in payload["venues"] if not row["ok"]} == {"binance", "hyperliquid"}
    assert payload["oi"]["total_usd"] is not None


# ──────────────────────────────────────────────────────────────────────────────
# the store
# ──────────────────────────────────────────────────────────────────────────────

def test_the_open_interest_history_is_bounded_and_takes_no_junk():
    history = derivatives.OiHistory(max_samples=3)
    assert history.add("bybit", "BTCUSDT", 1000, 10.0) is True
    assert history.add("bybit", "BTCUSDT", 1000, 11.0) is True          # same stamp: replaces
    assert history.series("bybit", "BTCUSDT") == [(1000, 11.0)]
    assert history.add("bybit", "BTCUSDT", 2000, 0.0) is False          # a zero is not a reading
    assert history.add("bybit", "BTCUSDT", 3000, -5) is False
    assert history.add("bybit", "BTCUSDT", 4000, None) is False
    assert history.add("bybit", "BTCUSDT", 4000, "nan") is False
    for stamp in (5000, 6000, 7000):
        history.add("bybit", "BTCUSDT", stamp, float(stamp))
    assert [row[0] for row in history.series("bybit", "BTCUSDT")] == [5000, 6000, 7000]
    assert history.keys() == [("bybit", "BTCUSDT")]
    assert history.series("okx", "BTCUSDT") == []
    history.clear()
    assert history.keys() == [] and history.stored == 0


def test_a_repeated_venue_timestamp_is_the_same_reading_not_a_new_sample():
    """A venue that serves the same snapshot twice must not look like a flat open interest."""
    clock = {"now": NOW}
    history = derivatives.OiHistory()
    service = _clocked(_Stub(ALL_VENUES), clock, history=history)
    first = service.read("BTCUSDT")
    assert first["oi"]["samples"] == 1
    clock["now"] = NOW + 86_400_000
    repeated = service.read("BTCUSDT")
    assert history.series("bybit", "BTCUSDT") == [(BYBIT_TICKERS["time"], 55420.091)]
    assert repeated["venues"][0]["oi_change_pct"] is None               # one venue sample, no change
    # the cross-venue total is this app's own reading, so it IS stamped with our own clock
    assert repeated["oi"]["change_pct"] == pytest.approx(0.0, abs=0.001)
    assert repeated["oi"]["samples"] == 2


def test_a_fresh_venue_stamp_is_what_builds_a_venues_own_baseline():
    clock = {"now": NOW}
    history = derivatives.OiHistory()
    first = _clocked(_Stub(ALL_VENUES), clock, history=history)
    first.read("BTCUSDT")
    later_payload = json.loads(json.dumps(BYBIT_TICKERS))
    later_payload["time"] = NOW + 86_400_000
    later_payload["result"]["list"][0]["openInterest"] = "57000.0"
    table = dict(ALL_VENUES, **{"bybit.com": later_payload})
    clock["now"] = NOW + 86_400_000
    second = _clocked(_Stub(table), clock, history=history)
    payload = second.read("BTCUSDT")
    bybit = payload["venues"][0]
    assert bybit["oi_change_pct"] == pytest.approx((57000.0 - 55420.091) / 55420.091 * 100.0, abs=0.01)
    assert bybit["oi_span_s"] == pytest.approx(86_400.0, abs=1.0)
    assert "on the day" in payload["summary"], payload["summary"]


def test_a_venue_sample_is_stamped_with_the_venues_own_clock():
    """Bybit publishes a `time`; Hyperliquid does not — the two must not be stamped the same way."""
    service = _service(_Stub(ALL_VENUES), now=NOW + 30_000)
    service.read("BTCUSDT")
    assert service.history.series("bybit", "BTCUSDT")[0][0] == BYBIT_TICKERS["time"]
    assert service.history.series("hyperliquid", "BTCUSDT")[0][0] == NOW + 30_000
    assert service.history.series(derivatives.TOTAL_KEY, "BTCUSDT")[0][0] == NOW + 30_000


# ──────────────────────────────────────────────────────────────────────────────
# the routes
# ──────────────────────────────────────────────────────────────────────────────

def _client(monkeypatch, service):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setattr(derivatives, "_service", service)
    app = FastAPI()
    app.include_router(derivatives.router)
    return TestClient(app)


def test_the_routes_are_declared_on_the_modules_own_router():
    paths = [route.path for route in derivatives.router.routes]
    assert paths == ["/api/atlas/derivatives/{symbol}", "/api/atlas/derivatives/venues"]
    source = MODULE.read_text(encoding="utf-8")
    assert 'APIRouter(prefix="/api/atlas"' in source
    assert '@router.get("/derivatives/{symbol}")' in source, "the decorator shape the UI audit reads"
    assert '@router.post("/derivatives/venues")' in source
    assert "asyncio.to_thread" in source, "blocking venue I/O runs off the event loop"


def test_the_read_route_answers_the_documented_shape(monkeypatch):
    service = _service(_Stub(ALL_VENUES))
    client = _client(monkeypatch, service)
    response = client.get("/api/atlas/derivatives/BTCUSDT")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) >= {"ok", "symbol", "as_of_ms", "venues_asked", "venues_ok", "venues",
                            "funding", "oi", "basis", "summary", "errors", "settings"}
    row = payload["venues"][0]
    assert set(row) >= {"venue", "label", "instrument", "ok", "error", "notes", "funding_rate",
                        "funding_interval_h", "funding_apr_pct", "next_funding_ms",
                        "next_funding_in_s", "mark", "index", "basis_bps", "basis_apr_pct",
                        "open_interest", "open_interest_unit", "open_interest_usd", "oi_change_pct",
                        "ts_ms", "age_ms"}
    assert payload["symbol"] == "BTCUSDT"
    assert payload["settings"]["venues"] == list(derivatives.VENUES)
    # the venue list rides in the query: the read asks only for what was named
    asked = client.get("/api/atlas/derivatives/BTCUSDT?venues=bybit")
    assert asked.status_code == 200
    assert [r["venue"] for r in asked.json()["venues"]] == ["bybit"]


def test_the_read_route_refuses_an_instrument_it_has_none_of(monkeypatch):
    client = _client(monkeypatch, _service(_Stub(ALL_VENUES)))
    payload = client.get("/api/atlas/derivatives/%20%20").json()
    assert payload["ok"] is False
    assert payload["detail"] == "pick an instrument first — the derivatives read needs one"
    assert payload["error"] == payload["detail"]
    assert payload["venues"] == [] and payload["summary"] == ""


def test_the_read_route_refuses_a_venue_name_it_does_not_cover(monkeypatch):
    client = _client(monkeypatch, _service(_Stub(ALL_VENUES)))
    payload = client.get("/api/atlas/derivatives/BTCUSDT?venues=sonic").json()
    assert payload["ok"] is False
    assert "no venue this panel covers was named ('sonic')" in payload["detail"]
    assert "Bybit, Binance, OKX, Hyperliquid" in payload["detail"]
    assert payload["dropped_venues"] == ["sonic"]
    # one good name and one bad: the read runs on the good one and reports the other
    mixed = client.get("/api/atlas/derivatives/BTCUSDT?venues=sonic,bybit").json()
    assert mixed["ok"] is True
    assert [row["venue"] for row in mixed["venues"]] == ["bybit"]
    assert mixed["dropped_venues"] == ["sonic"]


def test_the_read_route_never_500s_when_nothing_answers(monkeypatch):
    client = _client(monkeypatch, _service(_Stub(default=OSError("connection reset by peer"))))
    response = client.get("/api/atlas/derivatives/BTCUSDT")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["detail"].startswith("no venue answered for BTCUSDT — ")
    assert "Traceback" not in response.text and "urllib" not in response.text


def test_the_read_route_answers_a_service_that_blows_up(monkeypatch):
    class _Broken:
        def read(self, symbol, cfg=None):
            raise RuntimeError("something nobody predicted")

    client = _client(monkeypatch, _Broken())
    payload = client.get("/api/atlas/derivatives/BTCUSDT").json()
    assert payload["ok"] is False
    assert payload["detail"].startswith("the derivatives read failed — ")
    assert "RuntimeError" not in payload["detail"]


def test_the_read_route_asks_the_venues_once_per_refresh_window(monkeypatch):
    service = _service(_Stub(ALL_VENUES))
    client = _client(monkeypatch, service)
    client.get("/api/atlas/derivatives/BTCUSDT")
    calls = len(service._fetch.urls)
    assert calls == 8, "one Bybit call, two Binance, four OKX, one Hyperliquid"
    client.get("/api/atlas/derivatives/BTCUSDT")                 # inside refresh_s: served from cache
    assert len(service._fetch.urls) == calls
    client.get("/api/atlas/derivatives/BTCUSDT?refresh=1")       # an explicit refresh does ask again
    assert len(service._fetch.urls) > calls


def test_the_reads_never_write_config_and_the_post_writes_only_the_venue_list(monkeypatch):
    from orderflow_system.desktop import config_store

    written: list[dict] = []
    monkeypatch.setattr(config_store, "merge_config", lambda block: written.append(block))
    monkeypatch.setattr(config_store, "save_config",
                        lambda cfg: pytest.fail("a route must not rewrite the whole config"))
    client = _client(monkeypatch, _service(_Stub(ALL_VENUES)))
    client.get("/api/atlas/derivatives/BTCUSDT")
    assert written == [], "a GET must never write config"
    stored = client.post("/api/atlas/derivatives/venues", json={"venues": ["bybit", "okx"]}).json()
    assert stored["ok"] is True and stored["venues"] == ["bybit", "okx"] and stored["dropped"] == []
    assert written == [{"derivatives": {"venues": ["bybit", "okx"]}}]
    assert "reading Bybit, OKX from now on" in stored["detail"]


def test_the_venue_post_refuses_a_list_it_cannot_honour(monkeypatch):
    from orderflow_system.desktop import config_store

    written: list[dict] = []
    monkeypatch.setattr(config_store, "merge_config", lambda block: written.append(block))
    client = _client(monkeypatch, _service(_Stub(ALL_VENUES)))
    payload = client.post("/api/atlas/derivatives/venues", json={"venues": ["sonic", "mt5"]}).json()
    assert payload["ok"] is False
    assert "'sonic', 'mt5'" in payload["detail"]
    assert "Bybit, Binance, OKX, Hyperliquid" in payload["detail"]
    assert payload["dropped"] == ["sonic", "mt5"]
    empty = client.post("/api/atlas/derivatives/venues", json={}).json()
    assert empty["ok"] is False and empty["detail"].startswith("name at least one venue")
    assert written == [], "a refused POST must not have written anything"


def test_the_venue_post_applies_even_when_the_store_will_not_take_it(monkeypatch):
    from orderflow_system.desktop import config_store

    def _explode(block):
        raise OSError("config.json is locked")

    monkeypatch.setattr(config_store, "merge_config", _explode)
    client = _client(monkeypatch, _service(_Stub(ALL_VENUES)))
    payload = client.post("/api/atlas/derivatives/venues", json={"venues": ["bybit"]}).json()
    assert payload["ok"] is False
    assert payload["detail"].startswith("the venue list could not be saved (")
    assert "config.json is locked" in payload["detail"]
    assert "OSError" not in payload["detail"]


def test_the_settings_block_is_read_not_written():
    stored = derivatives.settings()
    assert stored == derivatives.clean(stored)
    assert set(stored) == set(derivatives.DEFAULTS)


def test_requested_venues_answers_the_request_or_the_stored_block():
    cfg = derivatives.clean({"venues": ["bybit", "okx"]})
    assert derivatives.requested_venues("", cfg) == (["bybit", "okx"], [])
    assert derivatives.requested_venues("binance", cfg) == (["binance"], [])
    assert derivatives.requested_venues("binance, sonic", cfg) == (["binance"], ["sonic"])
    assert derivatives.requested_venues("sonic", cfg) == ([], ["sonic"])


def test_the_route_coroutine_stands_alone():
    """The handler is a plain coroutine over a worker thread — callable without an app around it."""
    async def scenario():
        derivatives._service = derivatives.DerivativesService(fetch=_Stub(ALL_VENUES),
                                                             now_ms=lambda: NOW)
        try:
            return await derivatives.derivatives_read("BTCUSDT", "", False)
        finally:
            derivatives._service = None

    payload = asyncio.run(scenario())
    assert payload["ok"] is True and payload["venues_ok"] == 4
    assert payload["summary"].startswith("funding is ")


# ──────────────────────────────────────────────────────────────────────────────
# the panel: one rule, two implementations
# ──────────────────────────────────────────────────────────────────────────────

def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def test_the_panel_files_exist():
    for path in (PANEL, SELFTEST, MODULE):
        assert path.is_file(), f"{path.name} is missing"


def test_the_panel_parses_as_javascript():
    proc = subprocess.run([_node(), "--check", str(PANEL)], capture_output=True, text=True,
                          encoding="utf-8", timeout=60)
    assert proc.returncode == 0, proc.stderr


def test_the_panel_selftest_passes():
    proc = subprocess.run([_node(), str(SELFTEST)], capture_output=True, text=True, encoding="utf-8",
                          timeout=180, cwd=str(ROOT))
    out = proc.stdout.strip()
    match = re.search(r"derivatives selftest: (\d+) ok, (\d+) failed", out)
    assert match, f"unexpected selftest output: {out!r}\n{proc.stderr}"
    ok, failed = int(match.group(1)), int(match.group(2))
    assert failed == 0, out
    assert ok >= 25, f"the self-test shrank to {ok} checks — expected the formatter and wording coverage"
    assert proc.returncode == 0


PARITY_CASES = {
    "funding": [
        {"available": True, "median_pct": 0.01, "median_interval_h": 8, "rate_apr_pct": 10.95,
         "median_apr_pct": 10.8873,
         "direction": "longs_pay", "crowded_long": False, "crowded_short": False},
        {"available": True, "median_pct": -0.0093, "median_interval_h": 4, "rate_apr_pct": -20.3,
         "median_apr_pct": -20.3,
         "direction": "shorts_pay", "crowded_long": False, "crowded_short": True},
        {"available": True, "median_pct": 0.0, "median_interval_h": 8, "rate_apr_pct": 0.0,
         "median_apr_pct": 0.0,
         "direction": "flat", "crowded_long": False, "crowded_short": False},
        {"available": True, "median_pct": 0.00125, "median_interval_h": 1, "rate_apr_pct": 10.95,
         "median_apr_pct": 10.95,
         "direction": "longs_pay", "crowded_long": False, "crowded_short": False},
        {"available": False},
    ],
    "oi": [
        {"change_pct": 3.2, "span_s": 86400, "window_s": 86400, "reason": ""},
        {"change_pct": -1.5, "span_s": 7200, "window_s": 86400, "reason": ""},
        {"change_pct": 0.01, "span_s": 86400, "window_s": 86400, "reason": ""},
        {"change_pct": 4.42, "span_s": 1200, "window_s": 86400, "reason": ""},
        {"change_pct": None, "span_s": None, "window_s": 86400, "reason": "only 12 s of samples so far"},
        {"change_pct": None, "window_s": 86400},
    ],
    "spans": [[86400, 86400], [72000, 86400], [7200, 86400], [5400, 86400], [1200, 86400],
              [90, 86400], [None, 86400]],
    "settings": {"venues": ["bybit", "binance", "okx", "hyperliquid"], "refresh_s": 60,
                 "oi_window_s": 86400, "crowded_apr_pct": 30.0, "flat_apr_pct": 5.0,
                 "history_max": 2880},
}


def test_the_javascript_sentence_is_the_python_sentence_string_for_string(tmp_path):
    """The panel rebuilds this sentence when a payload carries none; both halves must agree.

    The numbers go to both implementations as one JSON document, so a formatter that drifts (a sign,
    a decimal, the window's name) fails here rather than in front of a user. The first sentence is
    also spelled out literally below, so the wording a reader is promised is checked by eye too.
    """
    cases = dict(PARITY_CASES)
    case_file = tmp_path / "cases.json"
    case_file.write_text(json.dumps(cases), encoding="utf-8")
    script = (
        "const fs=require('fs');"
        f"const src=fs.readFileSync({json.dumps(str(PANEL))},'utf8');"
        "const win={};new Function('window','setInterval','fetch',src)(win,()=>0,undefined);"
        "const D=win.OFAPDERIV;"
        f"const cases=JSON.parse(fs.readFileSync({json.dumps(str(case_file))},'utf8'));"
        "process.stdout.write(JSON.stringify({"
        "funding: cases.funding.map((f)=>D.fundingText(f)),"
        "oi: cases.oi.map((o)=>D.oiText(o)),"
        "spans: cases.spans.map((s)=>D.spanText(s[0],s[1])),"
        "summaries: cases.funding.map((f,i)=>D.summaryText({funding:f,oi:cases.oi[i%cases.oi.length],"
        "settings:cases.settings}))}));")
    proc = subprocess.run([_node(), "-e", script], capture_output=True, text=True, encoding="utf-8",
                          timeout=120, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr
    from_js = json.loads(proc.stdout)

    assert from_js["funding"] == [derivatives.funding_text(case) for case in cases["funding"]]
    assert from_js["oi"] == [derivatives.oi_text(case) for case in cases["oi"]]
    assert from_js["spans"] == [derivatives.span_text(span, window) for span, window in cases["spans"]]
    assert from_js["summaries"] == [
        derivatives.summary_line(case, cases["oi"][index % len(cases["oi"])], cases["settings"])
        for index, case in enumerate(cases["funding"])]
    assert from_js["summaries"][0] == (
        "funding is +0.010%/8h (+10.9% annualised) with OI up 3.2% on the day — longs are paying to hold")
    assert from_js["summaries"][2] == (
        "funding is 0.000%/8h (0.0% annualised) with OI flat on the day — neither side is paying much "
        "(under 5% annualised)")
    assert from_js["summaries"][4] == "", "a read with no funding has no sentence, on either side"


def test_the_panel_only_drives_ids_the_wiring_hunk_carries():
    """The section markup the parent inserts and the ids the panel asks for must be one set."""
    source = PANEL.read_text(encoding="utf-8")
    looked_up = set(re.findall(r"el\('([A-Za-z0-9_]+)'\)", source))
    assert "symbolSelect" in looked_up, "the shell's instrument select is what the panel follows"
    own = {name for name in looked_up if name.startswith("derivatives")}
    assert len(own) >= 15, sorted(own)
    painted = {"derivativesOiTotal", "derivativesOiChange", "derivativesBasis"}
    for name in own | painted:
        assert name in source, name
    for name in painted:                     # painted from a field map, not looked up by name
        assert f"{name}:" in source, name


def test_the_panel_stores_nothing_and_reaches_for_no_engine_verb():
    source = PANEL.read_text(encoding="utf-8")
    for banned in ("localStorage", "sessionStorage", "indexedDB", "WebSocket", "EventSource",
                   "eval(", "/api/control/engine"):
        assert banned not in source, f"derivatives.js must not touch {banned}"
    assert source.count("setInterval(") == 1, "one timer for the panel"
    assert "OFAPPause.register" in source and "document.hidden" in source and "OFAP_PAUSED" in source


def test_the_module_never_imports_the_feed_stack_or_a_key():
    source = MODULE.read_text(encoding="utf-8")
    for banned in ("import websockets", "import aiohttp", "api_key", "api_secret", "Authorization"):
        assert banned not in source, f"derivatives.py must not carry {banned}"
    assert source.count("urlopen") == 1, "exactly one place opens a socket: the injected default fetch"
    assert source.count("merge_config") == 1, "exactly one write path, and it writes a venue list"
    assert "save_config" not in source


def test_the_default_fetch_is_http_and_the_one_route_that_needs_post_is_translated_there():
    """The seam's real implementation is pinned by its shape: no test here is online."""
    source = MODULE.read_text(encoding="utf-8")
    assert "def default_fetch(url: str" in source
    assert "urllib.request.urlopen(request, timeout=timeout_s)" in source
    assert "json.loads(response.read().decode(\"utf-8\"))" in source
    assert 'url.startswith(f"{HYPERLIQUID_REST}/info")' in source, "the POST-only route is translated"
    assert "parse_qsl" in source
    assert derivatives.TIMEOUT_S == 10.0
    assert "public endpoints" in derivatives.USER_AGENT, "the UA names what is calling and why"


def test_the_route_is_discoverable_by_the_ui_audit():
    """The audit's own scanner, not a copy of its regex — with the wiring note beside it."""
    spec = importlib.util.spec_from_file_location("audit_ui_refs", AUDIT)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    found = audit.routes_from(MODULE, "/api/atlas")
    assert found == {"/api/atlas/derivatives/{symbol}", "/api/atlas/derivatives/venues"}
    # the panel's two call sites are written literally, so the audit can resolve them as soon as the
    # module is in JS_FILES and this file is in the audit's route table (see the report's PARENT ACTIONS)
    source = PANEL.read_text(encoding="utf-8")
    assert "api('/api/atlas/derivatives/' +" in source
    assert "api('/api/atlas/derivatives/venues'," in source
    calls = set(re.findall(r"api\('(/api/[^']+)'", source))
    assert calls == {"/api/atlas/derivatives/", "/api/atlas/derivatives/venues"}
    known = {audit.normalise(route) for route in found}
    for call in calls:
        norm = audit.normalise(call)
        assert norm in known or norm + "/{param}" in known, call


def test_the_module_parses_and_its_docstring_names_every_route_it_uses():
    import ast

    source = MODULE.read_text(encoding="utf-8")
    ast.parse(source)
    for endpoint in ("/v5/market/tickers", "/fapi/v1/premiumIndex", "/fapi/v1/openInterest",
                     "/api/v5/public/funding-rate", "/api/v5/public/open-interest",
                     "/api/v5/public/mark-price", "/api/v5/market/index-tickers",
                     "/info?type=metaAndAssetCtxs"):
        assert endpoint in source, f"{endpoint} is used but not documented"
    for venue in derivatives.VENUES:
        assert venue in source
    assert "github" not in source.lower()


def test_a_stub_driven_read_is_the_whole_read():
    """The proof that nothing outside the injected fetch is doing work: this never opens a socket."""
    service = derivatives.DerivativesService(fetch=_Stub(ALL_VENUES), now_ms=lambda: NOW)
    payload = service.read("BTCUSDT")
    assert payload["ok"] is True
    assert service.reads == 1 and service.failures == 0
    assert payload["cache_max"] == derivatives.DEFAULTS["history_max"]


# ── §148 T5-F04/F08/F09: the flat threshold's home, the throw path, the computed OI ─────────────

def test_the_flat_threshold_travels_with_the_settings_not_the_payload():
    """The chip's flat state needs the user's threshold, and only the settings carry it.

    Measured before the fix: ``stripHtml`` read ``funding.flat_apr_pct``, a key ``funding_read``
    never emits, so no venue could ever be painted flat — and the selftest passed only because its
    fixture fed the impossible shape.
    """
    cfg = derivatives.clean({})
    funding = derivatives.funding_read(_funding_rows(("bybit", 0.2, 8.0), ("okx", 0.3, 8.0)), cfg)
    assert "flat_apr_pct" not in funding, "the funding read never carried the threshold"
    assert cfg["flat_apr_pct"] == derivatives.DEFAULTS["flat_apr_pct"] == 5.0

    source = PANEL.read_text(encoding="utf-8", errors="replace")
    assert "function stripHtml(funding, settings)" in source
    assert "stripHtml(funding, current.settings)" in source, "the call site passes the settings"
    assert "funding.flat_apr_pct" not in source, "the payload is not where the threshold lives"


def test_the_flat_words_say_the_default_when_a_caller_hands_nothing():
    """A bare cfg still gets words, not a TypeError (and never "under undefined%").

    Measured before the fix: ``direction_text({"direction": "flat"}, {})`` raised
    ``TypeError: unsupported format string passed to NoneType.__format__`` while the panel's twin
    said "under undefined% annualised" — reachable from any caller the route does not clean.
    """
    words = derivatives.direction_text({"direction": "flat"}, {})
    assert words == "neither side is paying much (under 5% annualised)", words
    assert derivatives.DEFAULTS["flat_apr_pct"] == 5.0
    assert "under 12% annualised" in derivatives.direction_text(
        {"direction": "flat"}, derivatives.clean({"flat_apr_pct": 12, "crowded_apr_pct": 30}))
    source = PANEL.read_text(encoding="utf-8", errors="replace")
    assert "settings.flat_apr_pct == null ? 5 :" in source, "the JS twin names the same default"


def test_hyperliquid_says_its_computed_open_interest_is_computed():
    """Hyperliquid's OI-USD is this app's arithmetic too, and the row says so.

    Measured before the fix: the note was appended for Binance's computed figure only, so
    Hyperliquid's identical arithmetic rode unlabelled into the row and the cross-venue total.
    """
    parsed = derivatives.parse_hyperliquid(
        {"meta_contexts": [
            {"universe": [{"name": "BTC"}]},
            [{"funding": "0.0000125", "openInterest": "1000.0", "oraclePx": "2.5", "markPx": "2.5"}],
        ]}, "BTC")
    assert parsed["problem"] == ""
    assert parsed["fields"]["open_interest_usd"] == pytest.approx(1000.0 * 2.5)
    assert any("computed from this venue's own open interest and mark" in note
               for note in parsed["notes"]), parsed["notes"]


def test_the_derivatives_cache_stays_bounded():
    """§148 T5-F-14: every distinct `symbol|venues` read used to stay resident for the process's
    lifetime — only a TTL test, never an eviction — against the module's own standard for
    `OiHistory`. The store now keeps the newest `CACHE_MAX` writes and drops the oldest."""
    import inspect

    route_src = inspect.getsource(derivatives.derivatives_read)
    assert "_cache_store(key" in route_src and "_cache[key] =" not in route_src
    saved = dict(derivatives._cache)
    try:
        derivatives._cache.clear()
        for index in range(derivatives.CACHE_MAX + 12):
            derivatives._cache_store(f"SYM{index}|bybit", float(index), {"index": index})
        assert len(derivatives._cache) == derivatives.CACHE_MAX, len(derivatives._cache)
        assert "SYM0|bybit" not in derivatives._cache, "the oldest writes go first"
        newest = f"SYM{derivatives.CACHE_MAX + 11}|bybit"
        assert newest in derivatives._cache and derivatives._cache[newest][0] == float(
            derivatives.CACHE_MAX + 11)
    finally:
        derivatives._cache.clear()
        derivatives._cache.update(saved)
