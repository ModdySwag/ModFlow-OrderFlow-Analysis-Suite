"""R7 pins: version ordering, the due test, asset choice, and the download's verify-then-name rule.

Nothing here touches the network: GitHub is a canned payload handed to an injected opener, which
is also how the failure paths (offline, rate limit, malformed payload) get exercised at all.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
from pathlib import Path

import pytest

from orderflow_system.desktop import updater as up


def _release(tag: str, *, prerelease: bool = False, draft: bool = False,
             assets: list | None = None, body: str = "notes") -> dict:
    return {
        "tag_name": tag, "name": tag, "draft": draft, "prerelease": prerelease,
        "published_at": "2026-09-17T00:00:00Z", "html_url": f"https://example/{tag}",
        "body": body, "assets": assets if assets is not None else [],
    }


def _asset(name: str, digest: str = "") -> dict:
    entry = {"name": name, "size": 10, "browser_download_url": f"https://example/{name}"}
    if digest:
        entry["digest"] = digest
    return entry


def _opener(payload) -> object:
    """An opener returning bytes (check) — download uses its own fake response below."""
    body = json.dumps(payload).encode("utf-8")
    return lambda url, timeout: body


# ── versions ─────────────────────────────────────────────────────────────────────────────────

def test_version_parsing_and_ordering():
    assert up.parse_version("v0.1.0-beta") == (0, 1, 0, 0, "beta")
    assert up.parse_version("1.2.3-rc.4")[:4] == (1, 2, 3, 4)
    assert up.parse_version("nightly") == (0, 0, 0, 0, "")
    # numbers first, then the channel: a stable build outranks its own beta
    assert up.version_rank("0.2.0") > up.version_rank("0.1.9")
    assert up.version_rank("0.1.0") > up.version_rank("0.1.0-beta")
    assert up.version_rank("v1.0.0") > up.version_rank("0.9.9")
    assert up.version_rank("garbage") < up.version_rank("0.0.1")


def test_is_newer_against_the_shape_the_artefacts_carry():
    assert up.is_newer("0.2.0", "0.1.0-beta") is True
    assert up.is_newer("0.1.0", "0.1.0-beta") is True          # beta -> stable is an upgrade
    assert up.is_newer("0.1.0-beta", "0.1.0-beta") is False
    assert up.is_newer("0.0.9", "0.1.0") is False


def test_local_version_reads_the_running_build():
    local = up.local_version()
    assert local["version"] and local["display"]
    assert local["display"].startswith(local["version"])


# ── settings ─────────────────────────────────────────────────────────────────────────────────

def test_clamp_update_settings_falls_back_on_junk():
    out = up.clamp_update_settings({"updates": {
        "mode": "AUTO-DOWNLOAD", "channel": "Nightly", "interval_hours": "0",
        "download_dir": "  D:/updates  ", "last_check_ms": "soon", "skipped_version": "x" * 200,
    }})
    assert out["mode"] == "check"                 # unknown mode -> the safe one
    assert out["channel"] == "stable"
    assert out["interval_hours"] == 1             # clamped up to the floor
    assert out["download_dir"] == "D:/updates"
    assert out["last_check_ms"] == 0
    assert len(out["skipped_version"]) == 40
    assert up.clamp_update_settings({}) == up.DEFAULT_SETTINGS
    assert up.clamp_update_settings({"updates": {"mode": "download"}})["mode"] == "download"


def test_check_due_respects_the_interval():
    now_ms = int(time.time() * 1000)
    assert up.check_due({"last_check_ms": 0, "interval_hours": 6}, now_ms=now_ms) is True
    fresh = {"last_check_ms": now_ms - 60_000, "interval_hours": 6}
    assert up.check_due(fresh, now_ms=now_ms) is False
    stale = {"last_check_ms": now_ms - 7 * 3600_000, "interval_hours": 6}
    assert up.check_due(stale, now_ms=now_ms) is True


def test_pick_asset_prefers_the_windows_installer():
    chosen = up.pick_asset([_asset("notes.txt"), _asset("ModFlow-0.2.0.zip"),
                            _asset("ModFlow-Setup-0.2.0.exe")])
    assert chosen["name"] == "ModFlow-Setup-0.2.0.exe"
    assert up.pick_asset([_asset("data.zip"), _asset("ModFlow-0.2.0.zip")])["name"] == "ModFlow-0.2.0.zip"
    assert up.pick_asset([]) is None
    assert up.pick_asset([{"name": "x", "browser_download_url": ""}]) is None


# ── the check ────────────────────────────────────────────────────────────────────────────────

def test_check_reports_a_newer_release_and_its_asset():
    payload = [_release("v0.2.0", assets=[_asset("ModFlow-Setup-0.2.0.exe", "sha256:abc123"),
                                          _asset("notes.txt")])]
    result = up.check_for_update(opener=_opener(payload))
    assert result["ok"] is True and result["update_available"] is True
    assert result["latest"]["version"] == "v0.2.0"
    assert result["latest"]["asset"]["name"] == "ModFlow-Setup-0.2.0.exe"
    assert result["latest"]["asset"]["sha256"] == "abc123"      # digest stripped of its prefix
    assert result["release_page"].endswith("/releases")


def test_check_ignores_drafts_and_prereleases_on_the_stable_channel():
    payload = [_release("v0.9.0", draft=True), _release("v0.3.0-beta", prerelease=True),
               _release("v0.2.0")]
    stable = up.check_for_update(opener=_opener(payload))
    assert stable["latest"]["version"] == "v0.2.0"
    pre = up.check_for_update(opener=_opener(payload), channel="prerelease")
    assert pre["latest"]["version"] == "v0.3.0-beta" and pre["update_available"] is True


def test_check_picks_the_newest_by_version_not_by_publish_order():
    payload = [_release("v0.3.0", assets=[]), _release("v0.2.9"), _release("v0.4.0")]
    result = up.check_for_update(opener=_opener(payload))
    assert result["latest"]["version"] == "v0.4.0"


def test_check_with_no_releases_is_a_clean_answer():
    result = up.check_for_update(opener=_opener([]))
    assert result["ok"] is True and result["latest"] is None and result["update_available"] is False


def test_check_failures_are_answers_never_raises():
    def boom(url, timeout):
        raise urllib.error.URLError("no route to host")

    offline = up.check_for_update(opener=boom)
    assert offline["ok"] is False and "URLError" in offline["error"]
    assert offline["update_available"] is False

    def limited(url, timeout):
        raise urllib.error.HTTPError(url, 403, "rate limited", {}, None)   # type: ignore[arg-type]

    rate = up.check_for_update(opener=limited)
    assert rate["ok"] is False and "rate limit" in rate["error"]

    malformed = up.check_for_update(opener=lambda url, timeout: b'{"not": "a list"}')
    assert malformed["ok"] is False and "not a list" in malformed["error"]


def test_check_of_the_running_build_is_not_an_update():
    mine = up.local_version()["display"]
    result = up.check_for_update(opener=_opener([_release("v" + mine)]))
    assert result["ok"] is True and result["update_available"] is False


# ── the download ─────────────────────────────────────────────────────────────────────────────

class _FakeResponse:
    """What `urlopen` gives back, in the two attributes the downloader reads."""

    def __init__(self, chunks: list[bytes], headers: dict | None = None):
        self._chunks = list(chunks)
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""


def _download_opener(payload: bytes, headers: dict | None = None):
    def open_(url, timeout):
        return _FakeResponse([payload], headers or {"Content-Length": str(len(payload))})

    return open_


def test_download_verifies_then_names_the_file(tmp_path):
    payload = b"installer-bytes" * 100
    digest = hashlib.sha256(payload).hexdigest()
    result = up.download_asset("https://example/ModFlow-Setup.exe", tmp_path,
                               name="ModFlow-Setup.exe", opener=_download_opener(payload),
                               expected_sha256=digest)
    assert result["ok"] is True and result["verified"] is True
    target = Path(result["path"])
    assert target.exists() and target.read_bytes() == payload
    assert not list(tmp_path.glob("*.part")), "the .part file must not survive a good download"


def test_download_rejects_a_bad_checksum_and_leaves_nothing_behind(tmp_path):
    payload = b"tampered"
    result = up.download_asset("https://example/x.exe", tmp_path, name="x.exe",
                               opener=_download_opener(payload), expected_sha256="00" * 32)
    assert result["ok"] is False and "checksum mismatch" in result["error"]
    assert not (tmp_path / "x.exe").exists() and not list(tmp_path.glob("*.part"))


def test_download_without_a_published_digest_says_unverified(tmp_path):
    result = up.download_asset("https://example/y.exe", tmp_path, name="y.exe",
                               opener=_download_opener(b"data"))
    assert result["ok"] is True and result["verified"] is False


def test_download_cannot_write_reports_the_reason(tmp_path):
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("file", encoding="utf-8")
    result = up.download_asset("https://example/z.exe", blocker, opener=_download_opener(b"data"))
    assert result["ok"] is False and "cannot write" in result["error"]


def test_download_network_failure_is_reported_not_raised(tmp_path):
    def boom(url, timeout):
        raise urllib.error.URLError("connection reset")

    result = up.download_asset("https://example/w.exe", tmp_path, opener=boom)
    assert result["ok"] is False and "URLError" in result["error"]
    assert not list(tmp_path.glob("*.part"))


def test_cache_round_trip(tmp_path):
    path = tmp_path / "update-cache.json"
    assert up.load_cache(path) == {}
    up.save_cache(path, {"ok": True, "checked_at_ms": 1})
    assert up.load_cache(path)["ok"] is True
    path.write_text("{not json", encoding="utf-8")
    assert up.load_cache(path) == {}            # a corrupt cache is simply not a cache


@pytest.mark.parametrize("value", ["", "   "])
def test_resolved_download_dir_defaults_to_the_app(value):
    settings = up.clamp_update_settings({"updates": {"download_dir": value}})
    assert up.resolved_download_dir(settings, "C:/cfg") == Path("C:/cfg") / "updates"
