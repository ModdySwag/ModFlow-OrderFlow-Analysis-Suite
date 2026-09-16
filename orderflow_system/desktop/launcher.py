"""
Desktop launcher — one process, one window, no terminal required.

    python -m orderflow_system.desktop            # native window (Windows/macOS/Linux)
    python -m orderflow_system.desktop --browser  # open in the default browser instead
    python -m orderflow_system.desktop --headless # server only (CI / smoke tests)

Architecture
------------
  main thread ──► pywebview window  (macOS Cocoa and Windows both require the
                                    GUI on the main thread)
  server thread ─► asyncio loop ─► uvicorn (repo dashboard app + control API)
                                 └► engine tasks (data feeds, analytics)
"""

from __future__ import annotations

import argparse
import logging
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from orderflow_system.desktop import config_store, logs, single_instance, windows as windows_mod

logger = logging.getLogger(__name__)

UI_DIR = Path(__file__).parent / "ui"


# ──────────────────────────────────────────────────────────────
# App assembly
# ──────────────────────────────────────────────────────────────

def build_app(port: int):
    """Repo dashboard app + control API + the desktop UI, all on one origin."""
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    from orderflow_system.dashboard.app import app as dashboard_app
    from orderflow_system.atlas.api import router as atlas_router
    from orderflow_system.desktop.edgar import router as fundamentals_router
    from orderflow_system.desktop.api import router

    dashboard_app.include_router(router)
    dashboard_app.include_router(atlas_router)
    dashboard_app.include_router(fundamentals_router)

    # The repo's NoCacheMiddleware only covers / and /static — extend it to the
    # desktop shell so UI edits are never served stale from the webview cache.
    from starlette.middleware.base import BaseHTTPMiddleware
    from fastapi import Request

    class DesktopNoCache(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            response = await call_next(request)
            if request.url.path.startswith("/desktop"):
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                response.headers["Pragma"] = "no-cache"
            return response

    dashboard_app.add_middleware(DesktopNoCache)

    @dashboard_app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"ok": True, "port": port}

    if (UI_DIR / "index.html").is_file() and not any(
        getattr(r, "path", "") == "/desktop" for r in dashboard_app.routes
    ):
        dashboard_app.mount("/desktop", StaticFiles(directory=str(UI_DIR), html=True), name="desktop-ui")

        @dashboard_app.get("/desktop", include_in_schema=False)
        async def desktop_index():
            return FileResponse(str(UI_DIR / "index.html"))

        # R7 (P3-3): the legacy dashboard page retires as the front door — "/" belongs to the
        # desktop shell now. The page's files stay on disk (six of the nine static modules are
        # loaded by the desktop UI itself); only the default landing changes, and reversibly:
        # delete this block to bring the old page back.
        from fastapi.responses import RedirectResponse

        dashboard_app.router.routes = [
            r for r in dashboard_app.router.routes
            if not (getattr(r, "path", "") == "/"
                    and "GET" in (getattr(r, "methods", None) or set()))
        ]

        @dashboard_app.get("/", include_in_schema=False)
        async def legacy_root_redirect():
            return RedirectResponse(url="/desktop", status_code=307)

    return dashboard_app


def free_port(preferred: int) -> int:
    """Use the configured port when free, otherwise the next free one."""
    for candidate in [preferred] + list(range(preferred + 1, preferred + 20)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", candidate))
                return candidate
            except OSError:
                continue
    return 0


# ──────────────────────────────────────────────────────────────
# Server thread
# ──────────────────────────────────────────────────────────────

def serve(app, host: str, port: int, started: threading.Event) -> None:
    import uvicorn

    # log_config=None → uvicorn's own handlers are skipped and its records reach
    # the root logger (file + buffer). Uvicorn's default config attaches a
    # StreamHandler to sys.stderr, which is None under pythonw.exe — that is the
    # difference between a working shortcut and a window that never appears.
    config = uvicorn.Config(app, host=host, port=port, log_level="info", loop="asyncio", log_config=None)
    server = uvicorn.Server(config)

    def _mark_started() -> None:
        while not getattr(server, "started", False):
            time.sleep(0.05)
        started.set()

    threading.Thread(target=_mark_started, daemon=True).start()
    try:
        server.run()
    except Exception:
        logger.exception("Web server exited")
        started.set()


def wait_ready(port: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1):
                return True
        except Exception:
            time.sleep(0.15)
    return False


# ──────────────────────────────────────────────────────────────
# Window geometry (§72) — remembered per user, chosen per monitor
# ──────────────────────────────────────────────────────────────
#
# The window used to open at a fixed 1500×940 with a 1080×680 minimum: it could not fit a
# 1024×640 or 1366×768@150% work area, and it ignored where the user had left it — so a
# multi-monitor user re-placed it on every start. The choice is a pure function of
# (stored geometry, the screens that exist), which is why it lives here and not in main():
# every branch below is unit-tested without a GUI.

#: The taskbar / menu bar / dock a work area is never the whole screen.
WINDOW_CHROME_H = 56
#: Below this the shell cannot show its bars; above it a window is wider than any desktop.
WINDOW_MIN_W, WINDOW_MIN_H = 720, 480
#: A hard floor *under* the design minimum: on a work area smaller than the shell's own floor
#: (a 1366×768 display at 150% reports ~911×512, and a 512-tall work area minus the taskbar is
#: 456), the work area wins — an app-level minimum that produces a window which does not fit its
#: screen is the one geometry a user cannot rescue.
WINDOW_HARD_MIN = (320, 240)
#: The pre-§72 minimum — kept for the no-screens (headless) path, where nothing can be measured.
WINDOW_LEGACY_MIN = (1080, 680)


def _screen_rect(screen) -> dict | None:
    """One pywebview Screen (or any object with x/y/width/height) → a plain rect, or None."""
    try:
        rect = {"x": int(screen.x), "y": int(screen.y),
                "width": int(screen.width), "height": int(screen.height)}
    except (AttributeError, TypeError, ValueError):
        return None
    if rect["width"] <= 0 or rect["height"] <= 0:
        return None
    return rect


def screen_rects(screens) -> list[dict]:
    """The screens that exist, as rects, in the order the platform lists them (primary first)."""
    return [r for r in (_screen_rect(s) for s in (screens or [])) if r]


def pick_window_geometry(stored: dict | None, screens) -> dict:
    """Stored window geometry + the screens that exist → the geometry to open with.

    Rules, in order: a stored position wins while a screen still contains it — an unplugged
    monitor must never place the window off-desktop; otherwise the primary screen. The size and
    the minimum are both clamped to the chosen screen, so a small display gets a small-but-usable
    window instead of a 1500×940 one the user must rescue.
    """
    rects = screen_rects(screens)
    node = stored if isinstance(stored, dict) else {}
    try:
        want_w = int(node.get("width", 1500))
    except (TypeError, ValueError):
        want_w = 1500
    try:
        want_h = int(node.get("height", 940))
    except (TypeError, ValueError):
        want_h = 940
    want_x = node.get("x") if isinstance(node.get("x"), int) else None
    want_y = node.get("y") if isinstance(node.get("y"), int) else None
    maximised = bool(node.get("maximised", False))

    target = rects[0] if rects else None                 # pywebview lists the primary screen first
    if rects and want_x is not None and want_y is not None:
        for rect in rects:                               # the screen that still holds that origin
            if (rect["x"] <= want_x < rect["x"] + rect["width"]
                    and rect["y"] <= want_y < rect["y"] + rect["height"]):
                target = rect
                break

    if target is None:                                   # no screen to measure: exact pre-§72 behaviour
        width, height = max(WINDOW_MIN_W, want_w), max(WINDOW_MIN_H, want_h)
        return {"width": width, "height": height, "x": want_x, "y": want_y,
                "min_width": min(WINDOW_LEGACY_MIN[0], width),
                "min_height": min(WINDOW_LEGACY_MIN[1], height),
                "maximised": maximised}

    avail_w = max(WINDOW_HARD_MIN[0], target["width"])
    avail_h = max(WINDOW_HARD_MIN[1], target["height"] - WINDOW_CHROME_H)
    width = min(max(WINDOW_MIN_W, want_w), avail_w)
    height = min(max(WINDOW_MIN_H, want_h), avail_h)

    if want_x is not None and want_y is not None:
        x = min(max(want_x, target["x"]), target["x"] + target["width"] - width)
        y = min(max(want_y, target["y"]), target["y"] + target["height"] - WINDOW_CHROME_H - height)
    else:                                                # first run on this monitor: centred on it
        x = target["x"] + max(0, (target["width"] - width) // 2)
        y = target["y"] + max(0, (target["height"] - WINDOW_CHROME_H - height) // 2)
    return {"width": width, "height": height, "x": x, "y": y,
            "min_width": min(WINDOW_LEGACY_MIN[0], avail_w),
            "min_height": min(WINDOW_LEGACY_MIN[1], avail_h),
            "maximised": maximised}


def remember_window(window, cfg_block: dict | None = None) -> None:
    """Persist the window's geometry when it closes (§72).

    The rect is tracked from the window's own moved/resized events — while the window still
    exists — and written ONCE on close, so dragging never touches the config file. A maximised
    window stores the flag and keeps the last *normal* rect (the maximised rect must not become
    the size it later restores to).
    """
    live: dict = {}
    if isinstance(cfg_block, dict):
        live.update({k: cfg_block.get(k) for k in ("x", "y", "width", "height") if cfg_block.get(k) is not None})
    live["maximised"] = bool(isinstance(cfg_block, dict) and cfg_block.get("maximised"))

    def note_rect(*_args) -> None:
        if live.get("maximised"):
            return                                       # a maximised rect is not the reopen size
        try:
            live.update(x=int(window.x), y=int(window.y),
                        width=int(window.width), height=int(window.height))
        except Exception:                                # pragma: no cover - window mid-teardown
            logger.debug("window geometry read failed", exc_info=True)

    def note_maximised(*_args) -> None:
        live["maximised"] = True

    def note_restored(*_args) -> None:
        live["maximised"] = False

    def subscribe(name: str, handler) -> None:
        event = getattr(window.events, name, None)
        if event is not None:
            event += handler

    for name in ("shown", "moved", "resized"):
        subscribe(name, note_rect)
    subscribe("maximized", note_maximised)
    subscribe("restored", note_restored)

    def write_back(*_args) -> None:
        note_rect()
        if not live.get("width") or not live.get("height"):
            return
        try:
            cfg = config_store.load_config()
            block = cfg.get("ui")
            if not isinstance(block, dict):
                block = cfg["ui"] = {}
            block["window"] = config_store.clean_window(live)
            config_store.save_config(cfg)
        except Exception:                                # pragma: no cover - closing must never hang
            logger.debug("window geometry save failed", exc_info=True)

    subscribe("closed", write_back)


# ──────────────────────────────────────────────────────────────
# Auxiliary windows (§73) — the native side of the window seam
# ──────────────────────────────────────────────────────────────

def _webview():
    """pywebview, imported where it is used (the module must stay importable without a GUI)."""
    import webview

    return webview


class NativeWindowHost(windows_mod.WindowHost):
    """Creates and closes the real auxiliary windows.

    Geometry arrives already placed (`windows.place_aux`), so this class decides nothing about
    *where* a window goes — it opens where it is told, keeps the store's geometry current while the
    user drags it, and removes the window from the set when it closes (either side).

    Called from the API thread once the GUI is running; pywebview marshals window creation to its
    own loop, which is why nothing here touches the GUI directly.
    """

    kind = "pywebview"

    def __init__(self, port: int, title: str = "") -> None:
        self.port = int(port)
        self.title = title or "ModFlow OrderFlow Analysis Suite"
        self._windows: dict = {}

    # ── what exists ──────────────────────────────────────────────────────────

    def screens(self) -> list[dict]:
        rows: list[dict] = []
        try:
            for screen in (getattr(_webview(), "screens", None) or []):
                row = {"x": int(getattr(screen, "x", 0) or 0), "y": int(getattr(screen, "y", 0) or 0),
                       "width": int(getattr(screen, "width", 0) or 0),
                       "height": int(getattr(screen, "height", 0) or 0)}
                scale = getattr(screen, "scale", None)
                if scale:
                    row["scale"] = float(scale)
                rows.append(row)
        except Exception:                          # no display, no backend: no screens is an answer
            logger.debug("screen enumeration failed", exc_info=True)
        return rows

    def open_ids(self) -> list[str]:
        return list(self._windows.keys())

    # ── what changes ─────────────────────────────────────────────────────────

    def open(self, record: dict) -> dict:
        """Create the window for one record. Already open → focused, never duplicated."""
        wid = str(record.get("id") or "")
        if not wid:
            raise ValueError("a window record needs an id")
        if wid in self._windows:
            self.focus(wid)
            return record
        url = "http://127.0.0.1:%d/desktop?aux=%s&win=%s" % (
            self.port, record.get("view") or "", wid)
        window = _webview().create_window(
            "%s — %s" % (self.title, str(record.get("view") or "").upper()),
            url,
            x=int(record.get("x") or 0),
            y=int(record.get("y") or 0),
            width=int(record.get("width") or windows_mod.DEFAULT_W),
            height=int(record.get("height") or windows_mod.DEFAULT_H),
            min_size=(config_store.AUX_MIN_W, config_store.AUX_MIN_H),
            on_top=bool(record.get("on_top")),
        )
        self._windows[wid] = window
        self._track(wid, window)
        logger.info("auxiliary window %s (%s) at %s,%s %sx%s", wid, record.get("view"),
                    record.get("x"), record.get("y"), record.get("width"), record.get("height"))
        return record

    def _track(self, wid: str, window) -> None:
        """Keep the store's geometry current, and let the set go when the window closes."""
        def note(*_args) -> None:
            try:
                windows_mod.update_geometry(wid, int(window.x), int(window.y),
                                            int(window.width), int(window.height))
            except Exception:                      # a window mid-teardown has no geometry
                logger.debug("aux geometry read failed", exc_info=True)

        def forget(*_args) -> None:
            self._windows.pop(wid, None)
            try:
                windows_mod.drop_record(wid)       # closed from either side, it leaves the set
            except Exception:
                logger.debug("aux close bookkeeping failed", exc_info=True)

        for name in ("shown", "moved", "resized"):
            event = getattr(window.events, name, None)
            if event is not None:
                event += note
        closed = getattr(window.events, "closed", None)
        if closed is not None:
            closed += forget

    def close(self, wid: str) -> bool:
        window = self._windows.pop(wid, None)
        if window is None:
            return False
        window.destroy()
        return True

    def focus(self, wid: str) -> bool:
        window = self._windows.get(wid)
        if window is None:
            return False
        try:
            window.restore()
            window.show()
        except Exception:
            logger.debug("aux focus failed", exc_info=True)
            return False
        return True

    def set_on_top(self, wid: str, on_top: bool) -> bool:
        window = self._windows.get(wid)
        if window is None:
            return False
        window.on_top = bool(on_top)
        return True


def restore_windows(port: int, title: str = "") -> NativeWindowHost:
    """Install the host and bring back the auxiliary windows that were open (§73).

    Restored *before* ``webview.start()`` so every window exists when the GUI comes up; a window
    whose stored monitor is gone is re-placed on the primary by `windows.place_aux`, and the
    clamped geometry is written back so the arrangement stays true.
    """
    host = NativeWindowHost(port, title)
    windows_mod.set_host(host)
    for record in windows_mod.records():
        try:
            placement = windows_mod.place_aux(record, host.screens(), count=len(host.open_ids()))
            host.open(placement)
            windows_mod.add_record(placement)      # the store keeps what was actually placed
        except Exception:
            logger.warning("could not restore window %s — dropping it", record.get("id"), exc_info=True)
            windows_mod.drop_record(record["id"])
    return host


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orderflow-desktop", description="ModFlow OrderFlow Analysis Suite — desktop app")
    parser.add_argument("--browser", action="store_true", help="open in the default browser instead of a native window")
    parser.add_argument("--headless", action="store_true", help="run the server only (no window)")
    parser.add_argument("--port", type=int, default=0, help="override the configured port")
    parser.add_argument("--view", default="", help="open a specific view (overview/chart/orderflow/depth/tape/signals/strategy/performance/instruments/settings/logs)")
    args = parser.parse_args(argv)

    cfg = config_store.load_config()
    logs.install(cfg.get("logging", {}).get("level", "INFO"))

    # N-1: one windowed instance per profile. A second launch finds the named mutex held, brings
    # the existing window forward and exits — it does NOT start a second server/engine over the
    # same config.json and database. Headless runs are exempt on purpose (the smoke recipes run
    # their own scratch APPDATA alongside the owner's window).
    if not args.headless and not single_instance.acquire_for_app(str(config_store.config_dir())):
        print("ModFlow OrderFlow Analysis Suite is already running — bringing it forward.", file=sys.stderr)
        return 0

    preferred = args.port or int(cfg.get("dashboard", {}).get("port", 8080))
    port = free_port(preferred)
    if port == 0:
        print("No free TCP port found in range — aborting.", file=sys.stderr)
        return 2

    app = build_app(port)
    started = threading.Event()
    threading.Thread(target=serve, args=(app, "127.0.0.1", port, started), daemon=True,
                     name="orderflow-server").start()

    if not wait_ready(port):
        print(f"Server failed to start on port {port}.", file=sys.stderr)
        return 3

    url = f"http://127.0.0.1:{port}/desktop"
    if args.view:
        url += f"#{args.view}"
    logger.info("OrderFlow desktop ready at %s", url)

    if args.headless:
        print(f"Headless mode — UI at {url} (Ctrl+C to stop)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return 0

    if args.browser:
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return 0

    try:
        import webview
    except ImportError:
        print("pywebview is not installed — falling back to the default browser.", file=sys.stderr)
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return 0

    # P60: the window/taskbar icon is the ModFlow badge (bundled with the UI dir, so the frozen
    # build resolves it through _MEIPASS the same way). pywebview takes the icon on start(), not on
    # create_window() — an absent file falls back to the default rather than erroring.
    _icon = Path(__file__).resolve().parent / "ui" / "app.ico"   # the WinForms backend needs a real .ico
    # §72: reopen where the user left the window — on the monitor they left it on. The screens are
    # read before the window exists; a backend that cannot report them falls back to the pre-§72
    # geometry (that branch of pick_window_geometry has its own tests).
    window_cfg = (cfg.get("ui") or {}).get("window")
    try:
        import webview as _webview_probe                          # already imported above when present
        screens = list(getattr(_webview_probe, "screens", []) or [])
    except Exception:
        screens = []
    geo = pick_window_geometry(window_cfg, screens)
    logger.info("Window %dx%d at %s,%s (min %dx%d) on %d screen(s)",
                geo["width"], geo["height"], geo["x"], geo["y"],
                geo["min_width"], geo["min_height"], len(screen_rects(screens)))
    window = webview.create_window(
        "ModFlow OrderFlow Analysis Suite",
        url,
        width=geo["width"],
        height=geo["height"],
        x=geo["x"],
        y=geo["y"],
        min_size=(geo["min_width"], geo["min_height"]),
        maximized=geo["maximised"],
    )
    remember_window(window, window_cfg)                           # §72: written back when it closes
    # §73: the auxiliary windows that were open come back where they were — before start(), so
    # every window exists when the GUI comes up.
    restore_windows(port)
    try:
        webview.start(icon=str(_icon) if _icon.is_file() else None)   # blocks on the main thread (required on macOS)
    except Exception as exc:                # missing WebView2 / no display → browser fallback
        print(f"Native window unavailable ({exc}); opening the browser instead.", file=sys.stderr)
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
