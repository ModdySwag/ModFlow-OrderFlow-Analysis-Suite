"""config_store: the GUI-only flags the front end relies on (Phase 2 — T16 + T19).

Pinned here:
  * the defaults ship the `ui` block (Alpaca banner dismissal + wizard resume point)
  * both survive a save/load round-trip, and nonsense values are coerced
  * the `alpaca` block the wizard writes (paper flag, keys, symbol list) survives a
    round-trip with the symbol list normalised and capped

The store is the only place front-end state is persisted, so these rules are what
keep "Not now" and "resume the assistant" from silently resetting.
"""

from __future__ import annotations

import json

import pytest

from orderflow_system.desktop import config_store


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """A store whose config directory is a temp dir (never the user's real one)."""
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


def test_defaults_carry_the_ui_block(store):
    cfg = store.default_config()
    assert cfg["ui"]["banner_dismissed_alpaca"] is False
    assert cfg["ui"]["wizard_resume_step"] == 0
    assert cfg["alpaca"]["view_symbols"], "the Alpaca default symbol list must not be empty"


def test_ui_flags_survive_a_round_trip(store):
    cfg = store.load_config()
    cfg["ui"]["banner_dismissed_alpaca"] = True
    cfg["ui"]["wizard_resume_step"] = 3
    store.save_config(cfg)

    on_disk = json.loads(store.config_path().read_text(encoding="utf-8"))
    assert on_disk["ui"]["banner_dismissed_alpaca"] is True
    assert on_disk["ui"]["wizard_resume_step"] == 3
    # …and they come back through a fresh load, which is what the UI reads
    reloaded = store.load_config()
    assert reloaded["ui"]["banner_dismissed_alpaca"] is True
    assert reloaded["ui"]["wizard_resume_step"] == 3


def test_ui_values_are_coerced(store):
    clean = store.save_config({"ui": {"banner_dismissed_alpaca": "yes", "wizard_resume_step": "7"}})
    assert clean["ui"]["banner_dismissed_alpaca"] is True
    assert clean["ui"]["wizard_resume_step"] == 7

    for bad in ("abc", None, -5, {}):
        clean = store.save_config({"ui": {"wizard_resume_step": bad}})
        assert clean["ui"]["wizard_resume_step"] == 0, f"{bad!r} must fall back to the start"


def test_wizard_alpaca_block_round_trips(store):
    """The exact shape the wizard's Alpaca step writes into the config."""
    clean = store.save_config({"alpaca": {"enabled": True, "paper": False, "key_id": " PK123 ",
                                          "secret": " s3cret ", "view_symbols": ["aapl", " tsla ", ""]}})
    assert clean["alpaca"]["enabled"] is True
    assert clean["alpaca"]["paper"] is False
    assert clean["alpaca"]["key_id"] == "PK123"
    assert clean["alpaca"]["secret"] == "s3cret"
    assert clean["alpaca"]["view_symbols"] == ["AAPL", "TSLA"]

    assert store.load_config()["alpaca"]["key_id"] == "PK123"


def test_alpaca_symbols_are_strings_only_and_capped(store):
    clean = store.save_config({"alpaca": {"view_symbols": ["AAPL", 5, None, "btc/usd"] + [f"S{i}" for i in range(40)]}})
    syms = clean["alpaca"]["view_symbols"]
    assert "5" not in syms and "NONE" not in syms
    assert syms[:2] == ["AAPL", "BTC/USD"]
    assert len(syms) == 30, "the free plan streams 30 symbols — cap the list there"

    # a non-list must not explode the save
    clean = store.save_config({"alpaca": {"view_symbols": "AAPL"}})
    assert clean["alpaca"]["view_symbols"] == []


def test_search_block_and_watchlist_round_trip(store):
    """Phase 4: the palette's memory — recents, pins, default view, sort, watchlist."""
    cfg = store.load_config()
    assert cfg["search"]["recents"] == [] and cfg["search"]["pins"] == []
    assert cfg["search"]["default_view"] == "orderflow"
    assert cfg["watchlist"] == []

    cfg["search"]["recents"] = ["aapl", " msft ", "", "btc/usd"]
    cfg["search"]["pins"] = ["nvda"]
    cfg["search"]["default_view"] = "tape"
    cfg["search"]["sort"] = "chg"
    cfg["watchlist"] = ["aapl", "btc/usd"]
    saved = store.save_config(cfg)

    assert saved["search"]["recents"] == ["AAPL", "MSFT", "BTC/USD"], "blank entries are dropped"
    assert saved["search"]["pins"] == ["NVDA"]
    assert saved["search"]["default_view"] == "tape"
    assert saved["search"]["sort"] == "chg"
    assert saved["watchlist"] == ["AAPL", "BTC/USD"]
    assert store.load_config()["search"]["recents"][0] == "AAPL"


def test_search_lists_are_capped_and_validated(store):
    clean = store.save_config({
        "search": {"recents": [f"S{i}" for i in range(40)], "pins": [f"P{i}" for i in range(60)],
                   "default_view": "nonsense", "sort": "sideways"},
        "watchlist": [f"W{i}" for i in range(90)] + ["AAPL", 5, None],
    })
    assert len(clean["search"]["recents"]) == 12
    assert len(clean["search"]["pins"]) == 30
    assert len(clean["watchlist"]) == 60
    assert clean["search"]["default_view"] == "orderflow", "an unknown view falls back to the default"
    assert clean["search"]["sort"] == "relevance"
    assert "5" not in clean["watchlist"] and "NONE" not in clean["watchlist"]


def test_watchlist_survives_bad_types(store):
    clean = store.save_config({"watchlist": "AAPL", "search": ["not", "a", "dict"]})
    assert clean["watchlist"] == []
    assert isinstance(clean["search"], dict) and clean["search"]["recents"] == []


def test_data_source_accepts_every_shipped_source(store):
    """alpaca/all are real sources now — the whitelist must not silently reset them."""
    for source in ("bybit", "mt5", "both", "alpaca", "all"):
        assert store.save_config({"data_source": source})["data_source"] == source
    assert store.save_config({"data_source": "nonsense"})["data_source"] == "bybit"
    assert store.save_config({"data_source": "ALPACA"})["data_source"] == "alpaca"


def test_alpaca_feed_setting_is_clamped(store):
    assert store.save_config({"alpaca": {"feed": "sip"}})["alpaca"]["feed"] == "sip"
    assert store.save_config({"alpaca": {"feed": "nonsense"}})["alpaca"]["feed"] == "iex"
    assert store.save_config({"alpaca": {"snapshot_seconds": 900}})["alpaca"]["snapshot_seconds"] == 60.0
    assert store.save_config({"alpaca": {"snapshot_seconds": "abc"}})["alpaca"]["snapshot_seconds"] == 5.0


def test_bad_types_in_any_block_do_not_break_saving(store):
    """A garbage value in any block must not brick the save (the store is the only
    writer of the user's settings, so a crash here loses everything)."""
    clean = store.save_config({"ui": "nonsense", "alpaca": 5, "risk": [], "dashboard": "8080",
                               "telegram": None, "instruments": ["AAPL", 7, None]})
    for key in ("ui", "alpaca", "risk", "dashboard", "telegram"):
        assert isinstance(clean[key], dict), key
    assert clean["ui"]["wizard_resume_step"] == 0
    assert clean["risk"]["min_composite_score"] == 40.0
    assert clean["telegram"]["bot_token"] == ""
    assert clean["instruments"] == [], "non-mapping instrument entries are dropped, not passed on"


# ── the patch semantics of the settings write (2026-09-15) ────────────────────────────────────────────
# The trap: POST /api/control/config merged the body over the DEFAULTS, so posting one block reset every
# key it did not mention — measured live, {"ui": {"banner_dismissed_alpaca": true}} took
# search.default_view and context.fear_greed back to their factory values along with it.
def test_a_partial_write_patches_instead_of_resetting(store):
    cs = store
    cs.save_config({"search": {"default_view": "chart"},
                    "context": {"news": False, "fear_greed": False}})
    stored = cs.merge_config({"ui": {"banner_dismissed_alpaca": True}})
    assert stored["ui"]["banner_dismissed_alpaca"] is True
    assert stored["search"]["default_view"] == "chart", "an unrelated block was reset by a partial write"
    assert stored["context"]["news"] is False
    assert stored["context"]["fear_greed"] is False
    assert cs.load_config()["search"]["default_view"] == "chart", "the patch did not reach disk"


def test_a_block_level_write_can_still_remove_a_key(store):
    """merge_config patches; save_config must keep writing exactly what it is given, because the layout
    delete path removes an entry by posting the remaining block (test_layouts depends on it)."""
    cs = store
    cs.save_config({"layouts": {"items": {"a": {"name": "a"}, "b": {"name": "b"}}}})
    after = cs.save_config({"layouts": {"items": {"a": {"name": "a"}}}})
    assert list(after["layouts"]["items"]) == ["a"], "save_config stopped being a whole-block write"
