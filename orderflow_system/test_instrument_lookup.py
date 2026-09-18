"""§82 — the instrument look-up's pure rules: aliasing, states, actions, suggestions.

The panel trusts this module to never invent a stream, so the pins are about honesty:
an alias may only point at a shipped row, every action must be in the closed set, the
refusal a user reads must be the same string the engine writes into its `skipped` report,
and an unknown symbol must stay unknown while still offering its close matches.
"""

from __future__ import annotations

import pytest

from orderflow_system.desktop import config_store, engine, instrument_lookup as IL


def _rows() -> list[dict]:
    return [dict(i) for i in config_store.default_config()["instruments"]]


def _row(symbol: str, rows: list[dict] | None = None) -> dict:
    """The live row object, not a copy — tests mutate it to set up a state."""
    for row in rows if rows is not None else _rows():
        if row["symbol"] == symbol:
            return row
    raise AssertionError(f"{symbol} is not a shipped instrument row")


# ── normalise / alias ────────────────────────────────────────────────────────────────

def test_normalise_trims_upper_cases_and_unquotes():
    assert IL.normalise("  nq1! ") == "NQ1!"
    assert IL.normalise("'nas100'") == "NAS100"
    assert IL.normalise(None) == ""
    assert IL.normalise("a  b") == "A B"


@pytest.mark.parametrize("typed,expected", [
    ("NQ", "NAS100USDT"),
    ("nq1!", "NAS100USDT"),          # TradingView continuous notation
    ("NQZ25", None),                  # a real contract month is not in the table — stays unknown
    ("USTECm", "NAS100USDT"),         # Exness-style broker suffix
    ("US100", "NAS100USDT"),
    ("GOLD", "XAUUSDT"),
    ("WTI", "USOIL"),
    ("BTCUSDT", None),                # exact symbols are the caller's job, not the alias table's
    ("", None),
])
def test_alias_target(typed, expected):
    assert IL.alias_target(typed) == expected


def test_every_alias_points_at_a_shipped_row():
    """An alias may never invent a stream: each target must be a real config row."""
    shipped = {row["symbol"] for row in _rows()}
    dangling = sorted({target for target in IL.ALIASES.values() if target not in shipped})
    assert dangling == [], f"alias targets with no shipped row: {dangling}"


def test_the_bybit_list_stays_derived():
    """`_bybit_ish` reads the store's own list — this is the assertion that it is not a copy."""
    assert IL._bybit_ish() == frozenset(config_store.BYBIT_FALLBACK_SYMBOLS)


# ── resolve: the states ──────────────────────────────────────────────────────────────

def test_live_when_enabled_and_streaming():
    rows = _rows()
    nas = _row("NAS100USDT", rows)
    nas["enabled"] = True
    out = IL.resolve("NQ1!", instruments=rows, engine_symbols=["NAS100USDT"], source="mt5", running=True)
    assert out["state"] == "live"
    assert out["symbol"] == "NAS100USDT"
    assert out["via"] == "alias"
    assert out["actions"] == ["use"]
    assert "NAS100USDT" in out["reason"]


def test_ready_when_enabled_but_the_engine_is_stopped():
    rows = _rows()
    _row("NAS100USDT", rows)["enabled"] = True
    out = IL.resolve("NAS100USDT", instruments=rows, source="mt5", running=False)
    assert out["state"] == "ready"
    assert out["actions"] == ["use", "start_engine"]
    assert "stopped" in out["reason"]


def test_disabled_says_so_and_offers_enable():
    out = IL.resolve("NAS100USDT", instruments=_rows(), source="mt5", running=True,
                     engine_symbols=["BTCUSDT"])
    assert out["state"] == "disabled"
    assert out["actions"] == ["enable", "open_instruments"]


def test_unsupported_carries_the_engines_own_words_for_a_bybit_source():
    rows = _rows()
    _row("NAS100USDT", rows)["enabled"] = True
    out = IL.resolve("NQ", instruments=rows, source="bybit", running=True, engine_symbols=["BTCUSDT"])
    assert out["state"] == "unsupported"
    _selected, skipped = engine.select_instruments({"data_source": "bybit", "instruments": [{
        "symbol": "NAS100USDT", "enabled": True, "tick_size": 1.0, "patterns": {},
        "bybit_symbol": "", "mt5_symbol": "USTECm",
    }]})
    assert skipped and skipped[0]["reason"] == out["reason"], "panel and engine must refuse in one voice"


def test_available_when_the_broker_lists_the_name():
    out = IL.resolve("NQZ25", instruments=_rows(), source="mt5", running=True,
                     mt5_known=["NQZ25", "EURUSDm"])
    assert out["state"] == "available"
    assert out["actions"] == ["add", "open_instruments"]
    assert "MT5" in out["reason"]


def test_a_broker_name_is_not_available_on_a_crypto_source():
    out = IL.resolve("NQZ25", instruments=_rows(), source="bybit", running=True,
                     mt5_known=["NQZ25"])
    assert out["state"] == "unknown"


def test_unknown_keeps_suggestions_and_closed_actions():
    out = IL.resolve("NOTAREALINSTRUMENT", instruments=_rows(), source="bybit", running=True)
    assert out["state"] == "unknown"
    assert out["actions"] == ["open_instruments"]
    assert out["suggestions"] == []


def test_unknown_nasdaq_ish_query_suggests_the_index_row():
    out = IL.resolve("NAS99", instruments=_rows(), source="mt5", running=False)
    assert out["state"] == "unknown"
    symbols = [row["symbol"] for row in out["suggestions"]]
    assert "NAS100USDT" in symbols
    assert all(action in IL.ACTIONS for action in out["actions"])


def test_every_state_the_module_can_emit_is_declared():
    seen = set()
    for query, kwargs in [
        ("BTCUSDT", {}),
        ("NAS100USDT", {"running": True, "engine_symbols": ["BTCUSDT"]}),
        ("NQ", {"source": "bybit", "running": True, "engine_symbols": ["BTCUSDT"]}),
        ("NQZ25", {"source": "mt5", "running": True, "mt5_known": ["NQZ25"]}),
        ("???", {}),
        ("", {}),
    ]:
        rows = _rows()
        for row in rows:
            row["enabled"] = row["symbol"] in ("BTCUSDT", "NAS100USDT")
        seen.add(IL.resolve(query, instruments=rows, **kwargs)["state"])
    assert seen <= set(IL.STATES), f"undeclared states: {seen - set(IL.STATES)}"


def test_the_reported_case_nq_on_the_exchange_feed_answers_crypto_only_and_the_way_out():
    """The user's own query: NQ on the Bybit lane. The panel must answer with the engine's own
    sentence AND the step out of it — never "enable it" (the engine would skip it anyway)."""
    out = IL.resolve("NQ1!", instruments=_rows(), source="bybit", running=False)
    assert out["state"] == "unsupported"
    assert out["reason"] == "Bybit perps list crypto only — switch to MT5 (Windows) for this instrument"
    assert "MetaTrader 5" in out["hint"]
    assert out["actions"] == ["open_instruments"]
    assert out["symbol"] == "NAS100USDT", "the alias still names the row that would stream it"


def test_an_enabled_row_on_a_source_that_cannot_carry_it_is_not_called_ready():
    """'enabled — start the engine' would be a lie on a feed the engine refuses the row on."""
    rows = _rows()
    _row("NAS100USDT", rows)["enabled"] = True
    out = IL.resolve("NAS100USDT", instruments=rows, source="bybit", running=False)
    assert out["state"] == "unsupported"
    assert "crypto only" in out["reason"]
    assert out["actions"] == ["open_instruments"]


def test_empty_query_is_answered_not_crashed():
    out = IL.resolve("", instruments=_rows())
    assert out["state"] == "unknown"
    assert out["reason"] == "type an instrument name"


# ── broker spellings are per-broker and case-sensitive (measured against a real terminal) ──

def test_a_brokers_own_spelling_is_offered_as_the_replacement_mapping():
    """MetaQuotes lists US500M; the shipped default mapping is the Exness-style US500m.
    Typing the broker's own name must offer the remap, not a dead end."""
    rows = _rows()
    _row("SP500", rows)["mt5_symbol"] = "US500m"
    out = IL.resolve("US500M", instruments=rows, source="mt5", running=False,
                     mt5_known=["US500M", "USTEC", "EURUSD"])
    assert out["symbol"] == "SP500"
    assert out["state"] == "disabled"
    assert out["actions"] == ["add", "open_instruments"]
    assert out["broker_name"] == "US500M", "the broker's exact spelling is what gets written"
    assert "US500M" in out["reason"]


def test_a_mapping_the_broker_lists_keeps_the_plain_enable_action():
    rows = _rows()
    _row("SP500", rows)["mt5_symbol"] = "US500M"
    out = IL.resolve("SP500", instruments=rows, source="mt5", running=False,
                     mt5_known=["US500M"])
    assert out["state"] == "disabled"
    assert out["actions"] == ["enable", "open_instruments"]
    assert out["broker_name"] == "US500M"


def test_an_enabled_row_with_a_missing_mapping_offers_the_fix_not_a_usepath():
    rows = _rows()
    row = _row("SP500", rows)
    row["enabled"] = True
    row["mt5_symbol"] = "US500m"
    out = IL.resolve("US500M", instruments=rows, source="mt5", running=False,
                     mt5_known=["US500M"])
    assert out["state"] == "ready"
    assert out["actions"] == ["add", "start_engine"]
    assert "re-add it" in out["reason"]


def test_without_a_broker_list_the_row_keeps_its_own_mapping_and_no_nagging():
    rows = _rows()
    _row("SP500", rows)["mt5_symbol"] = "US500m"
    out = IL.resolve("SP500", instruments=rows, source="mt5", running=False)
    assert out["actions"] == ["enable", "open_instruments"]
    assert out["broker_name"] == "US500m"


def test_a_broker_only_name_keeps_its_exact_case():
    out = IL.resolve("ustec", instruments=_rows(), source="mt5", running=False,
                     mt5_known=["USTEC"])
    assert out["state"] == "disabled" or out["state"] == "live" or out["state"] == "ready"
    assert out["broker_name"] in ("USTEC", "USTECm")
    assert out["symbol"] == "NAS100USDT"


def test_a_stale_default_mapping_is_remapped_from_the_rows_own_market_names():
    """The shipped defaults are Exness-style (USTECm); a MetaQuotes demo lists USTEC. Typing
    the row's own name must still surface the broker's spelling as the fix."""
    rows = _rows()
    _row("NAS100USDT", rows)["mt5_symbol"] = "USTECm"
    out = IL.resolve("NAS100USDT", instruments=rows, source="mt5", running=False,
                     mt5_known=["USTEC", "EURUSD"])
    assert out["state"] == "disabled"
    assert out["actions"] == ["add", "open_instruments"]
    assert out["broker_name"] == "USTEC"
    assert "USTEC" in out["reason"]


# ── §82-ext: the Alpaca asset list is a venue listing too ───────────────────────────

def test_a_linked_alpaca_asset_answers_available_with_its_own_door():
    """The reported loop: SPY (a US ticker only Alpaca lists) read "unknown" while the add
    endpoint would have taken it. With the account's asset list in hand it is available, and
    the door names Alpaca even from a Bybit session — the add must go to the venue that
    confirmed the name."""
    out = IL.resolve("SPY", instruments=_rows(), source="bybit",
                     alpaca_known=["SPY", "QQQ", "AAPL", "BTC/USD"])
    assert out["state"] == "available"
    assert out["symbol"] == "SPY" and out["broker_name"] == "SPY"
    assert out["add_source"] == "alpaca"
    assert out["actions"] == ["add", "open_instruments"]
    assert "Alpaca" in out["reason"]


def test_a_shipped_row_still_answers_from_the_config_first():
    """An Alpaca-listed name that IS a shipped row keeps its row verdict (the source gate),
    never the asset-list short cut."""
    out = IL.resolve("NVDA", instruments=_rows(), source="bybit", alpaca_known=["NVDA"])
    assert out["state"] == "unsupported" and out["add_source"] == ""


def test_without_the_asset_list_an_unknown_symbol_stays_unknown():
    out = IL.resolve("SPY", instruments=_rows(), source="bybit")
    assert out["state"] == "unknown"
    assert "add" not in out["actions"] and out["add_source"] == ""


def test_the_exchange_refusal_names_alpaca_when_the_row_maps_to_it():
    """NVDA on Bybit used to be told to go find MT5 — while Alpaca (linked, and where the row
    actually streams) was never named. Index rows keep the MT5 sentence."""
    hint = IL.source_fix_hint("bybit", False, _row("NVDA"))
    assert "Alpaca" in hint and "MetaTrader 5" in hint
    plain = IL.source_fix_hint("bybit", False, _row("NAS100USDT"))
    assert "Alpaca" not in plain and "MetaTrader 5" in plain
