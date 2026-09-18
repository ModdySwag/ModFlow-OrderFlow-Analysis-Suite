"""§83 — "I had to re-enter it": pins for user input that must survive a restart.

The reported case was the Alpaca key pair, and its root cause was a whole-config write built
from a *block*: `POST /api/control/alpaca/test {save:true}` called `save_config(cfg)` where
`cfg` was only the alpaca block, and `save_config` merges over the DEFAULTS — so validating
keys reset every other setting and parked the keys at the top level of the file, where the
next launch's `alpaca` block could not see them.

Pinned here:
  * no `save_config(...)` in the desktop package may write a block as if it were the config
  * validating + saving keys keeps every other setting and stores the pair under `alpaca`
  * an empty secret never erases a stored one (alpaca; the same rule the wizard's MT5 step uses)
  * the engine start/restart bodies patch the config instead of replacing it
  * the UI wires the Telegram master switch and the chart/log view state in both directions
  * the new `ui.chart` / `ui.logs` blocks are clamped
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest

from orderflow_system.desktop import api, config_store

DESKTOP = Path(__file__).parent / "desktop"
UI = DESKTOP / "ui"


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """A store whose config directory is a temp dir (never the user's real one)."""
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


# ── the guard ────────────────────────────────────────────────────────────────────────

def test_no_block_is_ever_saved_as_a_whole_config():
    """`save_config(X)` merges over the DEFAULTS: X must be the whole config (from
    load_config/default_config), or every key it does not mention is reset."""
    offenders: list[str] = []
    for py in sorted(DESKTOP.rglob("*.py")):
        lines = py.read_text(encoding="utf-8", errors="replace").splitlines()
        for idx, line in enumerate(lines):
            if "save_config(" not in line or line.lstrip().startswith("def "):
                continue
            if "load_config()" in line or "default_config()" in line:
                continue                                      # whole-config write on one line
            arg = re.search(r"save_config\(\s*([A-Za-z_][A-Za-z0-9_]*)", line)
            if not arg:
                continue
            var = arg.group(1)
            # the enclosing function: back to the nearest top-level def
            start = 0
            for back in range(idx - 1, -1, -1):
                if lines[back].startswith("def ") or lines[back].startswith("async def "):
                    start = back
                    break
            block = "\n".join(lines[start:idx])
            origin = ""
            for m in re.finditer(rf"\s*{re.escape(var)}\s*=\s*(.+)$", block, re.M):
                origin = m.group(1)
            if "load_config()" not in origin and "default_config()" not in origin:
                offenders.append(f"{py.name}:{idx + 1}  {var} = {origin[:70]}")
    assert offenders == [], ("a block is being saved as a whole config — that resets every "
                            "setting the block does not mention:\n  " + "\n  ".join(offenders))


# ── the reported case ────────────────────────────────────────────────────────────────

def test_validate_and_save_keeps_every_other_setting(store, monkeypatch):
    """The exact call the "Validate & save" button makes."""
    from orderflow_system.desktop import alpaca as alpaca_mod

    cfg = store.load_config()
    cfg["watchlist"] = ["ZZZUSDT"]
    cfg["ui"]["theme"] = "light"
    cfg["instruments"][0]["enabled"] = True
    store.save_config(cfg)

    monkeypatch.setattr(alpaca_mod, "probe", lambda body: {"ok": True, "message": "fine"})
    out = asyncio.run(api.alpaca_test({"key_id": "PKTEST123", "secret": "s3cret", "paper": True,
                                       "save": True}))
    assert out["ok"] is True and out["saved"] is True

    on_disk = json.loads(store.config_path().read_text(encoding="utf-8"))
    assert on_disk["alpaca"]["key_id"] == "PKTEST123"
    assert on_disk["alpaca"]["secret"] == "s3cret"
    assert on_disk["alpaca"]["enabled"] is True
    # …and nothing else moved
    assert on_disk["watchlist"] == ["ZZZUSDT"]
    assert on_disk["ui"]["theme"] == "light"
    assert on_disk["instruments"][0]["enabled"] is True
    # …and the keys are NOT parked at the top level (where the alpaca block could not see them)
    assert "secret" not in on_disk and "key_id" not in on_disk


def test_the_saved_keys_survive_the_next_load(store, monkeypatch):
    """What the next launch reads: `configured` must be true after a validate-and-save."""
    from orderflow_system.desktop import alpaca as alpaca_mod

    monkeypatch.setattr(alpaca_mod, "probe", lambda body: {"ok": True})
    asyncio.run(api.alpaca_test({"key_id": "PKABC", "secret": "topsecret", "save": True}))
    reloaded = store.load_config()
    assert reloaded["alpaca"]["key_id"] == "PKABC"
    assert reloaded["alpaca"]["secret"] == "topsecret"


def test_an_empty_secret_never_erases_a_stored_one(store):
    """Re-saving the key ID (or toggling paper) must not wipe the secret."""
    asyncio.run(api.alpaca_save({"key_id": "PK1", "secret": "keepme"}))
    out = asyncio.run(api.alpaca_save({"key_id": "PK2", "secret": ""}))
    assert out["ok"] is True
    cfg = store.load_config()
    assert cfg["alpaca"]["key_id"] == "PK2"
    assert cfg["alpaca"]["secret"] == "keepme", "an empty field must never erase a stored secret"


def test_engine_start_with_a_partial_body_patches_rather_than_replaces(store, monkeypatch):
    cfg = store.load_config()
    cfg["watchlist"] = ["KEEPUSDT"]
    store.save_config(cfg)

    async def _fake_start(_cfg):
        return {"ok": True, "state": "running", "symbols": []}

    from orderflow_system.desktop import engine as engine_mod
    monkeypatch.setattr(engine_mod.engine, "start", _fake_start)
    asyncio.run(api.engine_start({"risk": {"min_composite_score": 55}}))
    reloaded = store.load_config()
    assert reloaded["watchlist"] == ["KEEPUSDT"]
    assert reloaded["risk"]["min_composite_score"] == 55


# ── the UI wiring (both directions) ──────────────────────────────────────────────────

def _ui(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


def test_the_telegram_master_switch_is_restored_and_collected():
    src = _ui("ui.js")
    assert re.search(r'setTgEnabled[^\n]*\.checked\s*=', src), "the switch is never restored"
    assert re.search(r'cfg\.telegram\.enabled\s*=\s*![^\n]*setTgEnabled', src), \
        "the switch is never collected"


def test_the_view_state_is_saved_on_change_and_restored():
    src = _ui("ui.js")
    for control, key in (("rangeSelect", "range"), ("ovMarkers", "markers"),
                         ("ovVP", "vp"), ("logLevel", "level"), ("logAuto", "auto"),
                         ("tfSelect", "tf")):
        at = src.find(f'{control}").onchange')
        assert at >= 0, f"{control} has no onchange handler"
        window = src[at:at + 400]
        assert "saveUIState" in window, f"{control} is changed but never saved"
        assert f"{{{key}:" in window or f"{key}:" in window, f"{control} saves the wrong field"
    assert "c.ui.chart" in src and "chartUI.markers" in src, "chart state is never restored"
    assert "chartUI.tf" in src, "the chart timeframe is never restored"
    assert "c.ui.logs" in src and "logsUI.level" in src, "log state is never restored"


def test_the_settings_save_builds_on_a_fresh_config():
    src = _ui("ui.js")
    body = src.split("async function collectSettings()", 1)[1].split("async function saveSettings", 1)[0]
    assert "'/api/control/config'" in body, \
        "collectSettings must read the stored config before patching it (stale snapshots roll back)"


def test_the_alpaca_feed_save_patches_one_field():
    src = _ui("alpaca-card.js")
    body = src.split("async function alpFeedSave()", 1)[1].split("\n}", 1)[0]
    assert "body: { alpaca: { feed: feed } }" in body, \
        "the feed save must patch its own field, not re-post a stale whole config"


def test_the_alpaca_symbol_list_says_what_it_is():
    """The list is the Alpaca feed's own subscription set — not engine instruments. Saying so
    is what stops "I added SPY and nothing happened" (the reported loop)."""
    src = _ui("alpaca-card.js")
    assert "subscribes the Alpaca feed" in src, "the list no longer says what it subscribes"


def test_the_alpaca_card_switches_the_engine_source_in_one_click():
    src = _ui("alpaca-card.js")
    assert "'/api/control/source'" in src, "the source switch endpoint is gone"
    assert "body: { source: 'alpaca' }" in src, "the switch must post the alpaca source id"
    assert "alpUseSrc" in src and "alpFeedUseSrc" in src, "a one-click control is gone"
    assert "Use Alpaca as the engine source" in src, "the button's literal label is gone"
    assert "engine source: Alpaca" in src, "the state chip is gone"
    at = src.find("async function alpUseSource")
    assert at >= 0, "no handler behind the button"
    assert "alpOvRender();" in src[at:at + 1800], \
        "the card must re-render so the state chip replaces the button"


# ── the new config blocks ────────────────────────────────────────────────────────────

def test_chart_and_log_view_state_is_clamped(store):
    cfg = store.load_config()
    cfg["ui"]["chart"] = {"range": -5, "markers": "yes", "vp": 0, "tf": 7}
    cfg["ui"]["logs"] = {"auto": "no", "level": "trace"}
    saved = store.save_config(cfg)
    assert saved["ui"]["chart"] == {"range": 0, "markers": True, "vp": False, "tf": 60}
    assert saved["ui"]["logs"] == {"auto": True, "level": ""}

    cfg = store.load_config()
    cfg["ui"]["chart"]["range"] = 86_400
    cfg["ui"]["chart"]["tf"] = 300
    cfg["ui"]["logs"]["level"] = "error"
    saved = store.save_config(cfg)
    assert saved["ui"]["chart"]["range"] == 86_400
    assert saved["ui"]["chart"]["tf"] == 300
    assert saved["ui"]["logs"]["level"] == "ERROR"

    cfg = store.load_config()
    cfg["ui"]["chart"]["tf"] = 12_345                  # not a #tfSelect option
    saved = store.save_config(cfg)
    assert saved["ui"]["chart"]["tf"] == 60
