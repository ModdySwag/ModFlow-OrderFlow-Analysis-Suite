"""
Standalone dashboard launcher.
Run with: python -m orderflow_system.dashboard

Starts the web dashboard on http://localhost:8080 without requiring
a running data feed (MT5/Bybit). API endpoints return empty data
until the full system is started.
"""

import uvicorn
from orderflow_system.config.settings import DASHBOARD


def main():
    print("=" * 50)
    print("  ORDERFLOW DASHBOARD (Standalone)")
    print(f"  http://localhost:{DASHBOARD.port}")
    print("=" * 50)
    print()
    print("  API endpoints will return empty data until")
    print("  the full system is started with data feeds.")
    print()

    from orderflow_system.dashboard.app import app

    uvicorn.run(
        app,
        host=DASHBOARD.host,
        port=DASHBOARD.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
