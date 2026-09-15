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

from orderflow_system.desktop import config_store, logs

logger = logging.getLogger(__name__)

UI_DIR = Path(__file__).parent / "ui"


# ──────────────────────────────────────────────────────────────
# App assembly
# ──────────────────────────────────────────────────────────────

def build_app(port: int):
    """Repo dashboard app + control API + the desktop UI, all on one origin."""
    from fastapi import FastAPI
    from fastapi.responses import FileResponse, HTMLResponse
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

    if (UI_DIR / "index.html").is_file():
        dashboard_app.mount("/desktop", StaticFiles(directory=str(UI_DIR), html=True), name="desktop-ui")

        @dashboard_app.get("/desktop", include_in_schema=False)
        async def desktop_index():
            return FileResponse(str(UI_DIR / "index.html"))

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

    window = webview.create_window(
        "ModFlow OrderFlow Analysis Suite",
        url,
        width=1500,
        height=940,
        min_size=(1080, 680),
    )
    try:
        webview.start()                     # blocks on the main thread (required on macOS)
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
