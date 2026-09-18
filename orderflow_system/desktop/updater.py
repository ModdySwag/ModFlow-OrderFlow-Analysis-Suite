"""Program updates (R7): know a new build exists, get it, and never interrupt the work to say so.

The app ships from a public repository, so "is there a newer build?" is a question the GitHub
releases API answers with no account and no key. This module is that question, its answer, and the
download that follows it:

* **check** — the latest release (or newest prerelease when the user wants the channel), compared
  against the running build by a tolerant version parser that understands the ``0.1.0-beta`` shape
  the artefacts carry;
* **when** — a check happens on load and then no more often than the configured interval, because a
  releases endpoint is not a heartbeat; the interval is a setting and the last check is remembered;
* **quietly** — nothing here ever raises at the user: no network, a rate limit or a malformed
  payload all come back as ``ok: False`` with the reason, and the panel says "couldn't check" rather
  than pretending the build is current. The *interaction* rule is the UI's: it is told what to show
  and decides to wait until the user's hands are off the keyboard;
* **the download** — streamed to a ``.part`` file, verified against the release's own SHA-256 when
  the API carries one, then renamed. Verified-or-named, never verified-or-guessed.

Pure decisions (version comparison, asset choice, the due test, the settings clamps) are plain
functions so the tests pin them without a socket.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

#: The public repository the artefacts ship from. Owner-configurable in code only: this is the
#: product's own address, not a user preference.
REPO = "ModdySwag/ModFlow-OrderFlow-Analysis-Suite"
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases?per_page=20"
RELEASE_PAGE = f"https://github.com/{REPO}/releases"

#: Channel order for the same version number — a stable build outranks its own release candidates.
_CHANNEL_RANK = {"dev": 0, "alpha": 1, "beta": 2, "rc": 3, "": 4, "stable": 4, "final": 4}

DEFAULT_SETTINGS: dict[str, Any] = {
    "mode": "check",              # check = tell me; download = fetch the artefact too
    "interval_hours": 6,          # how often a check may run while the app is open
    "channel": "stable",          # stable = released builds; prerelease = betas too
    "download_dir": "",           # empty = <config>/updates
    "last_check_ms": 0,
    "skipped_version": "",        # "not this one" sticks across restarts
}


# ══════════════════════════════════════════════════════════════
# Versions
# ══════════════════════════════════════════════════════════════

def parse_version(text: str) -> tuple[int, int, int, int, str]:
    """``"v0.1.0-beta.2"`` -> ``(0, 1, 0, 2, "beta")`` — tolerant, never raises. Pure.

    Anything unparseable sorts lowest, so a junk tag can never look newer than a real build.
    """
    raw = str(text or "").strip().lower().lstrip("v")
    channel = ""
    for name in ("dev", "alpha", "beta", "rc"):
        if name in raw:
            channel = name
            break
    numbers = re.findall(r"\d+", raw)
    parts = [int(n) for n in numbers[:4]]
    while len(parts) < 4:
        parts.append(0 if len(parts) < 3 else 0)
    if not numbers:
        return (0, 0, 0, 0, "")
    return (parts[0], parts[1], parts[2], parts[3], channel)


def version_rank(text: str) -> tuple[int, int, int, int, int]:
    """A sortable tuple: numbers first, then the channel rank (stable > rc > beta > alpha)."""
    major, minor, patch, build, channel = parse_version(text)
    return (major, minor, patch, build, _CHANNEL_RANK.get(channel, 0))


def is_newer(candidate: str, current: str) -> bool:
    """Is ``candidate`` a later build than ``current``? Pure."""
    return version_rank(candidate) > version_rank(current)


def local_version() -> dict[str, str]:
    """What is running, in the words the About card and the artefacts use."""
    try:
        from orderflow_system import __version__

        version = str(__version__)
    except Exception:                                  # pragma: no cover - defensive
        version = "0.0.0"
    try:
        from orderflow_system.desktop.help import APP_CHANNEL

        channel = str(APP_CHANNEL)
    except Exception:                                  # pragma: no cover - defensive
        channel = ""
    display = f"{version}-{channel}" if channel else version
    return {"version": version, "channel": channel, "display": display}


# ══════════════════════════════════════════════════════════════
# Settings
# ══════════════════════════════════════════════════════════════

def clamp_update_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    """The ``updates`` block, clamped — junk falls back to the documented defaults. Pure."""
    raw = dict((cfg or {}).get("updates") or {})
    out = dict(DEFAULT_SETTINGS)
    out["mode"] = "download" if str(raw.get("mode") or "").strip().lower() == "download" else "check"
    out["channel"] = "prerelease" if str(raw.get("channel") or "").strip().lower() == "prerelease" else "stable"
    out["download_dir"] = str(raw.get("download_dir") or "").strip()
    out["skipped_version"] = str(raw.get("skipped_version") or "").strip()[:40]
    for key, lo, hi in (("interval_hours", 1, 720), ("last_check_ms", 0, 10**15)):
        try:
            out[key] = max(lo, min(hi, int(raw.get(key, DEFAULT_SETTINGS[key]))))
        except (TypeError, ValueError):
            out[key] = int(DEFAULT_SETTINGS[key])
    return out


def check_due(settings: dict[str, Any], *, now_ms: int) -> bool:
    """True when the interval has passed since the last check (or there never was one). Pure."""
    last = int(settings.get("last_check_ms") or 0)
    if last <= 0:
        return True
    return (now_ms - last) >= int(settings.get("interval_hours") or 6) * 3600_000


def pick_asset(assets: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """The artefact to fetch: the Windows installer first, then the zip, then whatever is there.

    Pure. Preference order is explicit so a release carrying notes, checksums and three builds
    still resolves to one file rather than to ``assets[0]``.
    """
    usable = [a for a in (assets or []) if str(a.get("browser_download_url") or "").strip()]
    if not usable:
        return None

    def score(asset: dict[str, Any]) -> tuple[int, int, int, str]:
        name = str(asset.get("name") or "").lower()
        if name.endswith(".exe"):
            kind = 0
        elif name.endswith(".zip"):
            kind = 1
        elif name.endswith((".msi", ".7z")):
            kind = 2
        else:
            kind = 3
        setup = 0 if ("setup" in name or "install" in name) else 1
        # Among equals, the artefact carrying the product's own name is the build; anything else
        # in the same class (notes bundle, source drop) loses. The name is the last key so the
        # choice is deterministic rather than "whichever the API listed first".
        product = 0 if any(token in name for token in ("modflow", "orderflow", "ofap")) else 1
        return (kind, setup, product, name)

    return sorted(usable, key=score)[0]


# ══════════════════════════════════════════════════════════════
# The check
# ══════════════════════════════════════════════════════════════

def _default_opener(url: str, timeout: float):            # pragma: no cover - the real wire
    request = urllib.request.Request(
        url, headers={"User-Agent": "ModFlow-OrderFlow-Analysis-Suite",
                      "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(request, timeout=timeout)


def _read(opener: Callable[..., Any], url: str, timeout: float) -> bytes:
    response = opener(url, timeout)
    data = response.read() if hasattr(response, "read") else response
    return bytes(data)


def check_for_update(*, opener: Optional[Callable[..., Any]] = None, now: Optional[float] = None,
                     channel: str = "stable", timeout: float = 12.0) -> dict[str, Any]:
    """Ask GitHub for the releases and answer one question: is there a newer build? Never raises.

    ``channel='prerelease'`` allows betas; ``stable`` ignores anything flagged prerelease. The
    newest candidate by version (not by publish date — a backport patch published later is still
    older than the release above it) wins.
    """
    opener = opener or _default_opener
    now_ms = int((now if now is not None else time.time()) * 1000)
    mine = local_version()
    out: dict[str, Any] = {
        "ok": False, "error": "", "checked_at_ms": now_ms, "current": mine,
        "latest": None, "update_available": False, "release_page": RELEASE_PAGE,
        "channel": "prerelease" if str(channel).lower() == "prerelease" else "stable",
    }
    try:
        payload = json.loads(_read(opener, RELEASES_URL, timeout).decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        out["error"] = (f"GitHub answered {exc.code}"
                        + (" — the unauthenticated rate limit (60 an hour) is spent; try later"
                           if exc.code in (403, 429) else ""))
        return out
    except Exception as exc:                           # noqa: BLE001 - offline is normal, not fatal
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    if not isinstance(payload, list):
        out["error"] = "the releases payload was not a list — the API may have changed"
        return out

    candidates: list[dict[str, Any]] = []
    for release in payload:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        if release.get("prerelease") and out["channel"] != "prerelease":
            continue
        tag = str(release.get("tag_name") or release.get("name") or "").strip()
        if tag:
            candidates.append(release)
    if not candidates:
        out["ok"] = True                                # a real answer: there are no releases yet
        out["error"] = ""
        return out

    newest = max(candidates, key=lambda r: version_rank(str(r.get("tag_name") or "")))
    tag = str(newest.get("tag_name") or "").strip()
    assets = [a for a in (newest.get("assets") or []) if isinstance(a, dict)]
    asset = pick_asset(assets)
    out["latest"] = {
        "version": tag,
        "name": str(newest.get("name") or tag),
        "published_at": str(newest.get("published_at") or ""),
        "prerelease": bool(newest.get("prerelease")),
        "html_url": str(newest.get("html_url") or RELEASE_PAGE),
        "notes": str(newest.get("body") or "")[:6000],
        "assets": [{
            "name": str(a.get("name") or ""),
            "size": int(a.get("size") or 0),
            "url": str(a.get("browser_download_url") or ""),
            "sha256": str((a.get("digest") or "")).removeprefix("sha256:"),
        } for a in assets],
        "asset": None if asset is None else {
            "name": str(asset.get("name") or ""),
            "size": int(asset.get("size") or 0),
            "url": str(asset.get("browser_download_url") or ""),
            "sha256": str((asset.get("digest") or "")).removeprefix("sha256:"),
        },
    }
    out["ok"] = True
    out["update_available"] = is_newer(tag, mine["display"]) or is_newer(tag, mine["version"])
    return out


# ══════════════════════════════════════════════════════════════
# Cache + download
# ══════════════════════════════════════════════════════════════

def cache_path(config_dir: Path | str) -> Path:
    """Where the last check is remembered, so a restart shows the answer instead of re-asking."""
    return Path(config_dir) / "update-cache.json"


def load_cache(path: Path | str) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def save_cache(path: Path | str, payload: dict[str, Any]) -> None:
    try:
        Path(path).write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    except OSError as exc:                             # pragma: no cover - defensive
        logger.debug("could not persist the update cache: %s", exc)


def default_download_dir(config_dir: Path | str) -> Path:
    """Downloads live with the app's own files unless the user points somewhere else."""
    return Path(config_dir) / "updates"


def resolved_download_dir(settings: dict[str, Any], config_dir: Path | str) -> Path:
    raw = str(settings.get("download_dir") or "").strip()
    return Path(raw) if raw else default_download_dir(config_dir)


def download_asset(url: str, dest_dir: Path | str, *, name: str = "", opener: Optional[Callable[..., Any]] = None,
                   expected_sha256: str = "", timeout: float = 60.0,
                   progress: Optional[Callable[[int, int], None]] = None) -> dict[str, Any]:
    """Stream one artefact into ``dest_dir``, verify, then name it. Returns what happened.

    The file is written as ``<name>.part`` and only renamed once the digest matches (or once there
    was no digest to match — in which case the result says ``verified: False`` and the caller is
    expected to show that). A mismatch deletes the partial file and reports both digests.
    """
    opener = opener or _default_opener
    folder = Path(dest_dir)
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "error": f"cannot write to {folder} — {exc.strerror or exc}"}
    leaf = Path(str(name) or url.split("/")[-1] or "modflow-update").name
    target = folder / leaf
    part = folder / (leaf + ".part")
    digest = hashlib.sha256()
    written = 0
    try:
        response = opener(url, timeout)
        total = int(getattr(response, "headers", {}) and response.headers.get("Content-Length") or 0)
        with part.open("wb") as handle:
            while True:
                block = response.read(262144)
                if not block:
                    break
                handle.write(block)
                digest.update(block)
                written += len(block)
                if progress is not None:
                    try:
                        progress(written, total)
                    except Exception:                  # noqa: BLE001 - a paint must not break a download
                        pass
    except Exception as exc:                           # noqa: BLE001
        part.unlink(missing_ok=True)
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    got = digest.hexdigest()
    verified = bool(expected_sha256) and got.lower() == str(expected_sha256).lower()
    if expected_sha256 and not verified:
        part.unlink(missing_ok=True)
        return {"ok": False, "error": f"checksum mismatch — expected {expected_sha256[:16]}…, "
                                      f"downloaded {got[:16]}…", "sha256": got}
    part.replace(target)
    logger.info("[update] downloaded %s (%d bytes, verified=%s)", target, written, verified)
    return {"ok": True, "path": str(target), "bytes": written, "sha256": got, "verified": verified}
