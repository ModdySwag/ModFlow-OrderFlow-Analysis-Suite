"""
Standalone dashboard launcher.
Run with: python -m orderflow_system.dashboard [--port N]

Starts the demo dashboard (deterministic demo data — the render test bed) without requiring a
running data feed (MT5/Bybit); the API answers from the demo generator until the full system
is started.

The port follows the desktop app's rule: --port wins, else the per-user config's
`dashboard.port` (what the Settings view writes), else the 8080 default. When the preferred
port is held by another process the next free one is used and printed — a busy port never
blocks the launch (this entry used to die with Errno 10048 when an unrelated process held
8080; measured).
"""

from __future__ import annotations

import argparse
import sys

import uvicorn

from orderflow_system.config.settings import DASHBOARD
from orderflow_system.desktop.launcher import free_port


def _configured_port() -> int:
    """The per-user config's dashboard port, clamped to the range the store itself enforces.

    `load_config()` never raises on bad input and this guard never raises on a broken store
    (a demo server must start even when the config file is nonsense); the clamp mirrors
    `config_store._sanitise` because the file is hand-editable.
    """
    try:
        from orderflow_system.desktop.config_store import load_config

        block = load_config().get("dashboard")
        port = int(block.get("port", DASHBOARD.port)) if isinstance(block, dict) else DASHBOARD.port
    except Exception:                       # a broken config must not block the demo server
        port = DASHBOARD.port
    return min(max(port, 1024), 65535)


def resolve_port(cli_port: int = 0) -> tuple[int, int]:
    """(preferred, actual): the configured port, and the one this launch will bind.

    `actual` is the first free candidate at or after `preferred`, found with the same
    `free_port` the desktop launcher uses (`orderflow_system.desktop.launcher`).
    """
    preferred = cli_port or _configured_port()
    return preferred, free_port(preferred)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="orderflow-dashboard",
                                     description="ModFlow OrderFlow Analysis Suite — standalone demo dashboard")
    parser.add_argument("--port", type=int, default=0,
                        help="preferred port (default: the configured dashboard port)")
    args = parser.parse_args(argv)
    if args.port and not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    preferred, port = resolve_port(args.port)
    if port == 0:
        print(f"No free TCP port at or after {preferred} — pass --port with another port.", file=sys.stderr)
        raise SystemExit(2)

    print("=" * 50)
    print("  ORDERFLOW DASHBOARD (Standalone)")
    print(f"  http://localhost:{port}")
    if port != preferred:
        print(f"  (port {preferred} is busy — using {port})")
    print("=" * 50)
    print()
    print("  API endpoints answer from the demo generator;")
    print("  the live pipeline runs via `python -m orderflow_system.main`.")
    print()

    from orderflow_system.dashboard.app import app

    uvicorn.run(
        app,
        host=DASHBOARD.host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
