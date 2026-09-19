"""The WebView2 profile's lifetime (MEM-F-01 / MEM-E-04 / MEM-F-02).

pywebview's default is a fresh private profile under %TEMP% per launch, removed only by its own
close hook — so every unclean exit orphaned ~24 MB (one was still on disk during the audit), and
the per-window close hook could even rmtree the shared folder under a live main window. The GUI
now passes one app-owned storage path, and boot reaps the legacy temp profiles.
"""

from __future__ import annotations

import sys
import time
import types


def test_the_boot_sweep_removes_only_old_temp_profiles(tmp_path):
    from orderflow_system.desktop import launcher

    now = time.time()
    old = tmp_path / "tmpAAA" / "EBWebView"
    fresh = tmp_path / "tmpBBB" / "EBWebView"
    unrelated = tmp_path / "tmpCCC" / "not-a-profile"
    for path in (old, fresh, unrelated):
        path.mkdir(parents=True)
    import os
    os.utime(old, (now - 3 * 86400, now - 3 * 86400))
    os.utime(fresh, (now - 60, now - 60))

    assert launcher.stale_webview_profiles(tmp_path, now) == [old]
    assert launcher.sweep_webview_profiles(tmp_path, now=now) == 1
    assert not old.exists()
    assert fresh.exists() and unrelated.exists(), "young and unrelated directories are untouched"


def test_main_hands_webview_one_app_owned_profile(monkeypatch, tmp_path):
    """The launcher must pass storage_path + private_mode=False — the whole fix, end to end."""
    from orderflow_system.desktop import launcher

    calls: dict = {}
    fake = types.ModuleType("webview")
    fake.screens = []

    class _Window:
        def __init__(self) -> None:
            self.events = types.SimpleNamespace()

    def fake_create_window(*args, **kwargs):
        calls["window"] = kwargs
        return _Window()

    def fake_start(**kwargs):
        calls["start"] = kwargs

    fake.create_window = fake_create_window
    fake.start = fake_start
    monkeypatch.setitem(sys.modules, "webview", fake)

    class _Host:
        def close_all(self) -> int:
            return 0

    monkeypatch.setattr(launcher, "free_port", lambda preferred: 8123)
    monkeypatch.setattr(launcher, "build_app", lambda port: object())
    monkeypatch.setattr(launcher, "serve", lambda app, host, port, started: started.set())
    monkeypatch.setattr(launcher, "wait_ready", lambda port, timeout=20.0: True)
    monkeypatch.setattr(launcher, "remember_window", lambda window, cfg_block=None: None)
    monkeypatch.setattr(launcher, "restore_windows", lambda port, title="", restore=True: _Host())
    monkeypatch.setattr(launcher, "_shutdown_engine", lambda port, timeout=5.0: None)
    monkeypatch.setattr(launcher.config_store, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(launcher.profiles_mod, "boot_apply", lambda: False)
    monkeypatch.setattr(launcher.single_instance, "acquire_for_app", lambda key: True)

    assert launcher.main([]) == 0

    storage = calls["start"].get("storage_path")
    assert storage, "the GUI must pass an explicit profile path"
    assert str(tmp_path) in storage
    assert calls["start"].get("private_mode") is False
    assert (tmp_path / "webview2").is_dir(), "the app owns and creates the profile directory"
