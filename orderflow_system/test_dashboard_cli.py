"""The standalone demo dashboard entry (`python -m orderflow_system.dashboard`) — its port rule.

Pinned here:
  * the precedence --port > per-user config `dashboard.port` > the 8080 settings default,
    with a hand-edited nonsense config clamped (or fallen back) instead of crashing;
  * a preferred port another process holds moves to the next free one instead of dying with
    Errno 10048 (the measured failure when an unrelated process sat on 8080);
  * the shared picker (`desktop.launcher.free_port`) also sees a holder that set SO_REUSEADDR
    — on Windows a probe that itself sets the flag binds such a port happily and answers it
    free, and the uvicorn bind that follows then fails, so the probe must be exclusive;
  * the gate itself: an allocator that only draws above 65000 (one CI runner did, skipping all
    five port-dependent tests at once) must not skip the run — the gate sweeps the band itself.
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
    """A currently-free loopback port low enough for the picker's +20 scan to stay in range.

    The OS's own ephemeral draw is not a guarantee: one CI runner answered every draw above 65000
    and all five port-dependent tests skipped in the same run. A draw that misses falls through to
    a sweep of the band itself, so the gate gives up only when the machine really has no port here.
    """
    for _ in range(10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port <= 65000:
            return port
    for port in range(65000, 61000, -1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
        except OSError:
            continue
        return port
    pytest.skip("no free loopback port in 61001-65000")


def _hold(port: int, *, reuse: bool) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if reuse:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port))
    s.listen(1)
    return s


def test_the_port_gate_sweeps_its_band_when_the_allocator_only_draws_high(monkeypatch):
    """One CI runner answered every bind(0) draw above 65000 — all five port-dependent tests
    skipped at once, and the gate counts in that run stopped being comparable. The gate must find
    the port itself rather than skip on the allocator's draws.
    """
    class AllHighDraws:
        """A socket whose ephemeral draws always answer above 65000 (that runner's shape)."""

        def __init__(self, *_args, **_kwargs):
            self._port = None

        def bind(self, addr):
            self._port = 65001 if addr[1] == 0 else addr[1]

        def getsockname(self):
            return ("127.0.0.1", self._port)

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    monkeypatch.setattr(socket, "socket", AllHighDraws)
    try:
        port = _low_free_port()
    except BaseException as exc:      # pytest.skip is a BaseException — a skipped pin must fail
        pytest.fail(f"the gate gave up on the allocator's draws: {exc!r}")
    assert 61001 <= port <= 65000, "the sweep must land inside the band the picker needs"


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
