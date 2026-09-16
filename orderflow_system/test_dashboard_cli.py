"""The standalone demo dashboard entry (`python -m orderflow_system.dashboard`) — its port rule.

Pinned here:
  * the precedence --port > per-user config `dashboard.port` > the 8080 settings default,
    with a hand-edited nonsense config clamped (or fallen back) instead of crashing;
  * a preferred port another process holds moves to the next free one instead of dying with
    Errno 10048 (the measured failure when an unrelated process sat on 8080);
  * the shared picker (`desktop.launcher.free_port`) also sees a holder that set SO_REUSEADDR
    — on Windows a probe that itself sets the flag binds such a port happily and answers it
    free, and the uvicorn bind that follows then fails, so the probe must be exclusive.
"""

from __future__ import annotations

import json
import socket

import pytest

from orderflow_system.config.settings import DASHBOARD
from orderflow_system.dashboard import __main__ as dashboard_cli
from orderflow_system.desktop import config_store
from orderflow_system.desktop.launcher import free_port


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """A store whose config directory is a temp dir (never the user's real one)."""
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


def _low_free_port() -> int:
    """A currently-free loopback port low enough for the picker's +20 scan to stay in range."""
    for _ in range(10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port <= 65000:
            return port
    pytest.skip("no low ephemeral port available")


def _hold(port: int, *, reuse: bool) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if reuse:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port))
    s.listen(1)
    return s


def test_the_default_is_the_settings_port(store, monkeypatch):
    monkeypatch.setattr(dashboard_cli, "free_port", lambda p: p)
    assert dashboard_cli.resolve_port(0) == (DASHBOARD.port, DASHBOARD.port)


def test_the_config_port_beats_the_default(store, monkeypatch):
    monkeypatch.setattr(dashboard_cli, "free_port", lambda p: p)
    config_store.save_config({"dashboard": {"port": 8123}})
    assert dashboard_cli.resolve_port(0) == (8123, 8123)


def test_the_cli_port_beats_the_config(store, monkeypatch):
    monkeypatch.setattr(dashboard_cli, "free_port", lambda p: p)
    config_store.save_config({"dashboard": {"port": 8123}})
    assert dashboard_cli.resolve_port(8099) == (8099, 8099)


def test_a_hand_edited_config_port_is_clamped(store, monkeypatch):
    monkeypatch.setattr(dashboard_cli, "free_port", lambda p: p)
    (store.config_path()).write_text('{"dashboard": {"port": 99}}', encoding="utf-8")
    assert dashboard_cli.resolve_port(0) == (1024, 1024)


def test_a_nonsense_config_port_falls_back_to_the_default(store, monkeypatch):
    monkeypatch.setattr(dashboard_cli, "free_port", lambda p: p)
    (store.config_path()).write_text(json.dumps({"dashboard": {"port": "nonsense"}}), encoding="utf-8")
    assert dashboard_cli.resolve_port(0) == (DASHBOARD.port, DASHBOARD.port)


def test_a_busy_preferred_port_moves_to_the_next_free_one(store):
    busy = _low_free_port()
    held = _hold(busy, reuse=False)
    try:
        preferred, port = dashboard_cli.resolve_port(busy)
    finally:
        held.close()
    assert preferred == busy
    assert port != busy, "the busy port must not be handed back"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:   # …and the answer really is free
        s.bind(("127.0.0.1", port))


def test_the_picker_sees_a_reuse_enabled_holder_too(store):
    busy = _low_free_port()
    held = _hold(busy, reuse=True)
    try:
        assert free_port(busy) != busy
    finally:
        held.close()


def test_a_free_port_is_kept(store):
    port = _low_free_port()
    assert free_port(port) == port


def test_main_runs_uvicorn_on_the_resolved_port(store, monkeypatch, capsys):
    port = _low_free_port()
    seen: dict = {}
    monkeypatch.setattr(dashboard_cli, "free_port", lambda p: p)
    monkeypatch.setattr(dashboard_cli.uvicorn, "run",
                        lambda app, host, port, log_level: seen.update(host=host, port=port))
    dashboard_cli.main(["--port", str(port)])
    assert seen == {"host": DASHBOARD.host, "port": port}
    assert f"http://localhost:{port}" in capsys.readouterr().out


def test_main_says_so_when_the_port_moves(store, monkeypatch, capsys):
    port = _low_free_port()
    monkeypatch.setattr(dashboard_cli, "free_port", lambda p: p + 1)
    monkeypatch.setattr(dashboard_cli.uvicorn, "run", lambda *a, **k: None)
    dashboard_cli.main(["--port", str(port)])
    out = capsys.readouterr().out
    assert f"(port {port} is busy — using {port + 1})" in out
