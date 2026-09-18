"""Safe start (T2) — the rescue path: no auxiliary windows return, and the boot is Classic.

Two halves. The launcher half is source-level on purpose (the alternative is actually running a
pywebview app inside the suite): the flag exists, it sets the server-visible environment variable,
and restore_windows can install the host without opening anything. The route half is behavioural:
the layouts endpoint answers Classic while the flag is set, without touching the store.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from orderflow_system.desktop import api, config_store

DESKTOP = Path(__file__).parent / "desktop"
LAUNCHER = DESKTOP / "launcher.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_the_launcher_ships_the_safe_flag_and_gates_the_restore():
    text = _text(LAUNCHER)
    assert '"--safe"' in text, "the flag is gone"
    assert "OFAP_SAFE_START" in text, "the server never learns about a safe start"
    assert "restore=not args.safe" in text, "the window restore is not gated"


def test_restore_windows_can_install_the_host_without_opening_anything():
    text = _text(LAUNCHER)
    assert 'def restore_windows(port: int, title: str = "", restore: bool = True)' in text
    assert "if not restore:" in text and "return host" in text


def test_a_safe_start_boots_classic_without_writing_the_store(monkeypatch):
    monkeypatch.setattr(config_store, "load_config",
                        lambda: {"layouts": {"mode": "terminal", "active": "", "items": {}}})
    monkeypatch.setenv("OFAP_SAFE_START", "1")
    res = asyncio.run(api.layouts_get())
    assert res["mode"] == "classic" and res["safe"] is True
    monkeypatch.delenv("OFAP_SAFE_START")
    res = asyncio.run(api.layouts_get())
    assert res["mode"] == "terminal" and "safe" not in res
