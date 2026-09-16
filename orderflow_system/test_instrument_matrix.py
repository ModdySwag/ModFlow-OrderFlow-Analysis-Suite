"""Instrument matrix invariants (Phase 5).

`config/settings.py` is the single source of truth for what instruments exist: the
engine, the config store's fallback list, the venue chips and the setup assistant all
read (or derive from) it. These tests pin that — a new instrument is a two-line change
that cannot half-land, and a venue symbol the app has never heard of still runs.
"""

from __future__ import annotations


from orderflow_system.config import settings as S
from orderflow_system.config.settings import CRYPTO_MAJORS, INSTRUMENT_SPECS, Instrument
from orderflow_system.desktop import api, config_store, engine


def test_every_shipped_non_crypto_instrument_has_a_spec_row():
    """A symbol with no Spec row silently falls back to the crypto bank — a stock with
    crypto thresholds is a bug nobody would notice until the patterns misfire."""
    non_crypto = [m for m in Instrument if m not in INSTRUMENT_SPECS]
    missing = sorted(m.value for m in non_crypto if not m.value.endswith("USDT"))
    assert missing == [], f"add a Spec row for: {missing}"


def test_crypto_majors_are_enum_members():
    """The matrix and the enum must agree: get_crypto_config() does Instrument(symbol)."""
    unknown = sorted(sym for sym in CRYPTO_MAJORS if sym not in {m.value for m in Instrument})
    assert unknown == [], f"add an Instrument member for: {unknown}"


def test_derived_lists_cover_the_matrix_without_duplicates():
    """Fallback list and venue chips are derived, not copied — this is the assertion
    that used to be a comment asking people to remember two more places."""
    assert len(config_store.BYBIT_FALLBACK_SYMBOLS) == len(set(config_store.BYBIT_FALLBACK_SYMBOLS))
    assert len(api.VENUE_MAJORS) == len(set(api.VENUE_MAJORS))
    assert "BTCUSDT" in config_store.BYBIT_FALLBACK_SYMBOLS
    missing = [s for s in CRYPTO_MAJORS
               if s not in config_store.BYBIT_FALLBACK_SYMBOLS or s not in api.VENUE_MAJORS]
    assert missing == [], f"a shipped major is missing from a derived list: {missing}"
    # the deliberate extra: Bybit delisted MATIC in favour of POL, old configs still resolve
    assert "MATICUSDT" in api.VENUE_MAJORS


def test_venue_only_symbol_gets_a_config_and_runs():
    """T45: the wizard can add any perpetual the venue lists. Before this, such an
    instrument was accepted into the config and then refused as "unknown instrument"."""
    cfg = S.config_for_symbol("WIFUSDT", 0.0001)
    assert cfg.instrument.value == "WIFUSDT"
    assert cfg.tick_size == 0.0001, "the venue's tick size must win over the bank"
    assert cfg.volume_profile.session is S.SessionType.FULL_DAY
    assert cfg.absorption.min_aggressive_volume == 20      # crypto bank

    spec = {"symbol": "WIFUSDT", "enabled": True, "bybit_symbol": "WIFUSDT",
            "tick_size": 0.0001, "patterns": {}}
    selected, skipped = engine.select_instruments({"data_source": "bybit", "instruments": [spec]})
    assert [c.instrument.value for c in selected] == ["WIFUSDT"]
    assert skipped == []


def test_unknown_symbol_is_still_refused_without_a_venue_stamp():
    """The ad-hoc path is gated on evidence: a symbol the venue confirmed. Without it,
    a typo must not become a crypto instrument."""
    spec = {"symbol": "NOTAREALSYMBOL", "enabled": True, "patterns": {}}
    selected, skipped = engine.select_instruments({"data_source": "bybit", "instruments": [spec]})
    assert selected == []
    assert skipped == [{"symbol": "NOTAREALSYMBOL", "reason": "unknown instrument"}]


def test_bybit_capable_prefers_the_config_over_the_shipped_list():
    assert engine.bybit_capable({"symbol": "WIFUSDT", "bybit_symbol": "WIFUSDT"})
    assert engine.bybit_capable({"symbol": "BTCUSDT"})              # shipped fallback
    assert not engine.bybit_capable({"symbol": "AAPL", "bybit_symbol": ""})


def test_overrides_do_not_bleed_between_engine_starts():
    """`_apply_overrides` wrote onto the cached base config, so a threshold changed for
    one start leaked into every later one (a GUI reset only took effect after a
    restart). select_instruments() must hand out copies."""
    loud = {"data_source": "bybit", "instruments": [{
        "symbol": "BTCUSDT", "enabled": True, "bybit_symbol": "BTCUSDT", "tick_size": 0.5,
        "patterns": {"absorption": {"min_aggressive_volume": 999}, "sweep": {"min_levels_swept": 9}},
    }]}
    quiet = {"data_source": "bybit", "instruments": [{
        "symbol": "BTCUSDT", "enabled": True, "bybit_symbol": "BTCUSDT", "patterns": {},
    }]}

    first = engine.select_instruments(loud)[0][0]
    assert first.tick_size == 0.5
    assert first.absorption.min_aggressive_volume == 999

    second = engine.select_instruments(quiet)[0][0]
    assert second.absorption.min_aggressive_volume == 20, "override leaked into the next start"
    assert second.sweep.min_levels_swept == 3
    assert second.tick_size == 0.01

    # …and the process-wide cache the whole app reads must be untouched too
    cached = engine.base_configs()["BTCUSDT"]
    assert cached.absorption.min_aggressive_volume == 20
    assert cached.tick_size == 0.01


def test_bad_override_values_fall_back_instead_of_raising():
    """The GUI can post a string where a float belongs; the engine keeps running."""
    spec = {"symbol": "BTCUSDT", "enabled": True, "bybit_symbol": "BTCUSDT",
            "tick_size": "not-a-number", "patterns": {"absorption": {"min_aggressive_volume": "nope"}}}
    selected, skipped = engine.select_instruments({"data_source": "bybit", "instruments": [spec]})
    assert skipped == []
    assert selected[0].absorption.min_aggressive_volume == 20
