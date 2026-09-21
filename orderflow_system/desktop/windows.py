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


#: The snap shapes a window can be given inside one screen's work area. These are the shapes the
#: OS itself offers (half, quarter, maximise) plus `center`, which is the shape a window keeps its
#: own size in — what "send this panel to the other monitor" means. The order is the order the
#: UI offers them in, so a menu never invents a shape the API cannot resolve.
PRESETS = ("left", "right", "top", "bottom",
           "topleft", "topright", "bottomleft", "bottomright", "fill", "center")


def work_area(rect: dict) -> dict:
    """One screen's usable rectangle: the screen minus the taskbar strip (§72's CHROME_H).

    A window is placed inside THIS, never inside the raw screen — a window that covers the taskbar
    is a window whose own title bar is one drag away from being unreachable.
    """
    return {"x": int(rect.get("x") or 0), "y": int(rect.get("y") or 0),
            "width": max(1, int(rect.get("width") or 0)),
            "height": max(1, int(rect.get("height") or 0) - CHROME_H)}


def preset_rect(rect: dict, preset: str, want_w: int = 0, want_h: int = 0) -> dict:
    """The rectangle a preset means inside one screen's work area — pure, so every shape is pinned.

    `want_w`/`want_h` are the window's own size: `center` honours them (a window that is *sent* to
    another monitor keeps its size), while the snap shapes take both axes from the screen. Every
    shape is floored at the window minimums first and then pulled back inside the work area, so a
    preset can never answer with a rectangle the store would refuse (on a display smaller than the
    minimums the floor wins and the clamp keeps the origin inside).
    """
    area = work_area(rect)
    W, H = area["width"], area["height"]
    key = str(preset or "center").strip().lower()
    if key not in PRESETS:
        key = "center"
    min_w, min_h = config_store.AUX_MIN_W, config_store.AUX_MIN_H

    def shape(w: int, h: int, x: int, y: int) -> dict:
        w = min(max(min_w, int(w)), W)
        h = min(max(min_h, int(h)), H)
        x = min(max(int(x), area["x"]), area["x"] + W - w)
        y = min(max(int(y), area["y"]), area["y"] + H - h)
        return {"x": x, "y": y, "width": w, "height": h}

    half_w, half_h = W // 2, H // 2
    right_x, bottom_y = area["x"] + half_w, area["y"] + half_h
    if key == "left":
        return shape(half_w, H, area["x"], area["y"])
    if key == "right":
        return shape(W - half_w, H, right_x, area["y"])
    if key == "top":
        return shape(W, half_h, area["x"], area["y"])
    if key == "bottom":
        return shape(W, H - half_h, area["x"], bottom_y)
    if key == "topleft":
        return shape(half_w, half_h, area["x"], area["y"])
    if key == "topright":
        return shape(W - half_w, half_h, right_x, area["y"])
    if key == "bottomleft":
        return shape(half_w, H - half_h, area["x"], bottom_y)
    if key == "bottomright":
        return shape(W - half_w, H - half_h, right_x, bottom_y)
    if key == "fill":
        return shape(W, H, area["x"], area["y"])
    try:
        want_w = int(want_w or 0) or DEFAULT_W
    except (TypeError, ValueError):
        want_w = DEFAULT_W
    try:
        want_h = int(want_h or 0) or DEFAULT_H
    except (TypeError, ValueError):
        want_h = DEFAULT_H
    return shape(want_w, want_h, area["x"] + max(0, (W - min(want_w, W)) // 2),
                 area["y"] + max(0, (H - min(want_h, H)) // 2))


def screen_index_of(screens, x, y) -> int | None:
    """Which screen contains a point, or None (a position on a monitor that is gone)."""
    if isinstance(x, bool) or isinstance(y, bool):
        return None
    try:
        px, py = float(x), float(y)
    except (TypeError, ValueError):
        return None
    for index, rect in enumerate(valid_screens(screens)):
        if (rect["x"] <= px < rect["x"] + rect["width"]
                and rect["y"] <= py < rect["y"] + rect["height"]):
            return index
    return None


def stranded(records, screens, live=None) -> list[str]:
    """Ids that need rescuing — from the store AND from the live windows, in listed order.

    Two sources, because the store can lag reality: a record whose stored position is on no screen
    (a monitor that is gone since the last session), and an OPEN window whose live position is (the
    window the OS left behind after an unplug, or one moved off-desktop by hand — measured live:
    the store still said (0, 0) while the window sat at (9000, 40), so the store alone missed
    exactly the case this rescue exists for). A record that was never placed (no x/y) is NOT
    stranded: it opens wherever placement decides.
    """
    rects = valid_screens(screens)
    if not rects:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def mark(wid) -> None:
        key = str(wid or "")
        if key and key not in seen:
            seen.add(key)
            out.append(key)

    for row in (records or []):
        if not isinstance(row, dict) or not row.get("id"):
            continue
        if row.get("x") is None or row.get("y") is None:
            continue
        if screen_index_of(rects, row.get("x"), row.get("y")) is None:
            mark(row["id"])
    for wid, rect in (live or {}).items():
        if not isinstance(rect, dict):
            continue
        if rect.get("x") is None or rect.get("y") is None:
            continue
        if screen_index_of(rects, rect.get("x"), rect.get("y")) is None:
            mark(wid)
    return out


def move_placement(record: dict, screens, screen_index: int | None = None,
                   preset: str = "center", step: int = 0) -> dict:
    """Where an EXISTING window goes when it is sent to a monitor — pure, and never a no-op.

    The caller is asking for a change, so unlike `place_aux` (where a stored position may win) this
    always resolves a real rectangle. The screen is chosen by an explicit `screen_index`, else by
    `step` screens from where the window is now (cyclic — the hotkey's "next monitor"), else by the
    screen that contains its current position, else the primary.
    """
    rects = valid_screens(screens)
    node = record if isinstance(record, dict) else {}
    out = dict(node)
    if not rects:
        out["x"] = out["y"] = None               # nothing to place against: shape only
        out["screen"] = -1
        out["screen_label"] = "no display"
        return out
    index = screen_index if isinstance(screen_index, int) and 0 <= screen_index < len(rects) else None
    if index is None:
        here = screen_index_of(rects, node.get("x"), node.get("y"))
        if here is not None and step:
            index = (here + int(step)) % len(rects)     # cyclic: the hotkey past the last screen
        elif here is not None:
            index = here
        else:
            index = 0
    target = rects[index]
    out.update(preset_rect(target, preset, want_w=node.get("width") or 0,
                           want_h=node.get("height") or 0))
    out["screen"] = index
    out["screen_label"] = screen_label(target, index, target.get("scale"))
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

    def move(self, wid: str, x: int, y: int, width: int, height: int) -> bool:
        """Put an open window at this rectangle. False when it is not open."""
        return False

    def geometry(self, wid: str) -> dict | None:
        """Where an open window is right now (x/y/width/height), or None when it is not open."""
        return None

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
