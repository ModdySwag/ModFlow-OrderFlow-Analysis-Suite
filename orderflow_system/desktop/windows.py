"""Auxiliary windows (§73) — one widget per native window, placed on a monitor.

The desktop app is one window with a board in it. A power user with a second monitor wants part of
that board *on* the second monitor, so the shell can ask for a window: this module is the seam
between the page (which decides *what* should be in a window) and the launcher (which owns the real
windows). Three pieces, in the order they are trusted:

  * **placement is a pure function** (`place_aux`): a screen that exists, a rectangle inside its
    work area, and a cascade so two windows opened in a row do not land on top of each other. Every
    branch is unit-tested without a GUI — the same shape §72 gave the main window.
  * **the host owns the windows.** The launcher installs one (`set_host`) when it has pywebview; in
    a browser, a headless session or a test there is none and the API answers `native: false`, so
    the shell never offers a control that cannot work.
  * **the open set is persisted** (`ui.windows`), so a launch restores the arrangement. The store
    owns the clamps (`config_store.clean_window_record`); this module reads and writes through it.

Nothing here starts a thread, draws anything, or knows about pywebview — the launcher's host does.
"""

from __future__ import annotations

import logging
import threading
import time

from orderflow_system.desktop import config_store

logger = logging.getLogger(__name__)

#: The taskbar/menu area a work area is never the whole screen (§72's constant, restated so this
#: module needs no import of the launcher).
CHROME_H = 56
#: The gap between two cascaded windows.
CASCADE_STEP = 28
#: A geometry change may touch the config file this often at most — a drag must not spin the disk.
SAVE_THROTTLE_S = 2.0
#: What a slot new window opens as, before the screen has a say.
DEFAULT_W, DEFAULT_H = 1100, 760


# ──────────────────────────────────────────────────────────────
# Placement — pure, so every branch is tested without a GUI
# ──────────────────────────────────────────────────────────────

def screen_label(rect: dict, index: int, scale: float | None = None) -> str:
    """How a screen is named to the user: "Monitor 1 · 2560×1440" (plus its scale when known)."""
    size = "%dx%d" % (int(rect.get("width") or 0), int(rect.get("height") or 0))
    label = "Monitor %d · %s" % (index + 1, size)
    try:
        factor = float(scale or 0)
    except (TypeError, ValueError):
        factor = 0.0
    if factor and abs(factor - 1.0) > 0.001:
        label += " · %g%%" % round(factor * 100, 1)
    return label


def valid_screens(screens) -> list[dict]:
    """The screens that can hold a window, as plain rects, primary first."""
    out: list[dict] = []
    for entry in (screens or []):
        if not isinstance(entry, dict):
            continue
        try:
            rect = {"x": int(entry.get("x") or 0), "y": int(entry.get("y") or 0),
                    "width": int(entry.get("width") or 0), "height": int(entry.get("height") or 0)}
        except (TypeError, ValueError):
            continue
        if rect["width"] <= 0 or rect["height"] <= 0:
            continue
        if entry.get("scale") is not None:
            rect["scale"] = entry.get("scale")
        out.append(rect)
    return out


def place_aux(record: dict, screens, count: int = 0, screen_index: int | None = None) -> dict:
    """Where an auxiliary window of this shape opens, inside one screen's work area.

    The screen is chosen in this order: an explicit `screen_index` (the user just picked a monitor
    in the menu), else a stored position **while a screen still contains it** (an unplugged monitor
    must never place a window off-desktop), else the primary. A *new* window (no stored position, or
    an explicit index) cascades by `count` steps so successive opens do not stack exactly.

    Returns the record with `x`/`y`/`width`/`height` resolved, plus `screen` (the index it landed
    on) and `screen_label` — both informational, and both dropped again by the store's sanitiser
    when the record is written, so nothing here can leak into the stored shape.
    """
    rects = valid_screens(screens)
    node = record if isinstance(record, dict) else {}
    out = dict(node)
    # Normalise the position once: `None` means "no stored position" (a fresh window), and the
    # branches below can then treat x/y uniformly.
    out["x"] = node.get("x") if isinstance(node.get("x"), int) else None
    out["y"] = node.get("y") if isinstance(node.get("y"), int) else None
    try:
        want_w = int(node.get("width") or 0) or DEFAULT_W
    except (TypeError, ValueError):
        want_w = DEFAULT_W
    try:
        want_h = int(node.get("height") or 0) or DEFAULT_H
    except (TypeError, ValueError):
        want_h = DEFAULT_H

    target = None
    index = 0
    explicit = False
    if rects:
        if isinstance(screen_index, int) and 0 <= screen_index < len(rects):
            target, index, explicit = rects[screen_index], screen_index, True
        else:
            x, y = node.get("x"), node.get("y")
            if isinstance(x, int) and isinstance(y, int):
                for i, rect in enumerate(rects):
                    if (rect["x"] <= x < rect["x"] + rect["width"]
                            and rect["y"] <= y < rect["y"] + rect["height"]):
                        target, index = rect, i
                        break
            if target is None:
                target, index = rects[0], 0

    if target is None:                      # headless / no screen to measure: size only
        out["width"] = max(config_store.AUX_MIN_W, want_w)
        out["height"] = max(config_store.AUX_MIN_H, want_h)
        out["screen"] = -1
        out["screen_label"] = "no display"
        return out

    avail_w = max(360, target["width"])
    avail_h = max(240, target["height"] - CHROME_H)
    width = min(max(config_store.AUX_MIN_W, want_w), avail_w)
    height = min(max(config_store.AUX_MIN_H, want_h), avail_h)

    x, y = node.get("x"), node.get("y")
    if isinstance(x, int) and isinstance(y, int) and not explicit:
        cx = min(max(x, target["x"]), target["x"] + target["width"] - width)
        cy = min(max(y, target["y"]), target["y"] + target["height"] - CHROME_H - height)
    else:
        step = (int(count) % 8) * CASCADE_STEP if count else 0
        cx = target["x"] + max(0, (target["width"] - width) // 2) + step
        cy = target["y"] + max(0, (target["height"] - CHROME_H - height) // 2) + step
        cx = min(max(cx, target["x"]), target["x"] + target["width"] - width)
        cy = min(max(cy, target["y"]), target["y"] + target["height"] - CHROME_H - height)

    out["x"], out["y"], out["width"], out["height"] = int(cx), int(cy), int(width), int(height)
    out["screen"] = index
    out["screen_label"] = screen_label(target, index, target.get("scale"))
    return out


# ──────────────────────────────────────────────────────────────
# The host — whatever owns the real windows (the launcher, usually)
# ──────────────────────────────────────────────────────────────

class WindowHost:
    """The contract the API needs. The launcher's implementation is the only real one."""

    #: Set by the implementation so the UI can say what kind of windows these are.
    kind = "none"

    def screens(self) -> list[dict]:
        """The screens that exist, as {x, y, width, height, scale?}, primary first."""
        return []

    def open(self, record: dict) -> dict:
        """Create the window for this record (geometry already resolved). Returns what it made."""
        raise NotImplementedError

    def close(self, wid: str) -> bool:
        """Close one window. False when it is not open."""
        return False

    def focus(self, wid: str) -> bool:
        return False

    def set_on_top(self, wid: str, on_top: bool) -> bool:
        return False

    def open_ids(self) -> list[str]:
        """Ids of the windows that are actually open right now."""
        return []


_LOCK = threading.RLock()
_HOST: WindowHost | None = None
_last_save = 0.0


def set_host(host: WindowHost | None) -> None:
    """Install the window host (the launcher does this; tests install a fake)."""
    global _HOST
    with _LOCK:
        _HOST = host


def get_host() -> WindowHost | None:
    with _LOCK:
        return _HOST


def native() -> bool:
    """True when real native windows can be created — false in a browser or headless session."""
    return get_host() is not None


# ──────────────────────────────────────────────────────────────
# The persisted set — `ui.windows`, the arrangement a launch restores
# ──────────────────────────────────────────────────────────────

def records() -> list[dict]:
    """The auxiliary windows that should be open, as the store keeps them."""
    cfg = config_store.load_config()
    return config_store.clean_windows((cfg.get("ui") or {}).get("windows"))


def _write(rows: list[dict]) -> list[dict]:
    """Store exactly these rows (clamped) and return what was stored."""
    with _LOCK:
        cfg = config_store.load_config()
        block = cfg.get("ui")
        if not isinstance(block, dict):
            block = cfg["ui"] = {}
        block["windows"] = config_store.clean_windows(rows)
        clean = config_store.save_config(cfg)
    return clean["ui"]["windows"]


def add_record(record: dict) -> list[dict]:
    """Append one record (replacing any with the same id) and persist. Returns the stored set."""
    rows = [r for r in records() if r["id"] != record["id"]]
    rows.append(record)
    return _write(rows[: config_store.WINDOWS_MAX])


def drop_record(wid: str) -> list[dict]:
    """Remove one window from the desired set (closed from either side) and persist."""
    keep = [r for r in records() if r["id"] != wid]
    return _write(keep)


def update_geometry(wid: str, x: int, y: int, width: int, height: int, force: bool = False) -> None:
    """Remember a moved/resized window, at most once per SAVE_THROTTLE_S unless forced."""
    global _last_save
    with _LOCK:
        now = time.monotonic()
        if not force and (now - _last_save) < SAVE_THROTTLE_S:
            return
        rows = records()
        hit = False
        for row in rows:
            if row["id"] == wid:
                row["x"], row["y"], row["width"], row["height"] = int(x), int(y), int(width), int(height)
                hit = True
        if not hit:
            return
        _last_save = now
    _write(rows)


def set_on_top(wid: str, on_top: bool) -> bool:
    """Remember a window's pinned state. False when no such window is in the set."""
    rows = records()
    hit = False
    for row in rows:
        if row["id"] == wid:
            row["on_top"] = bool(on_top)
            hit = True
    if hit:
        _write(rows)
    return hit
