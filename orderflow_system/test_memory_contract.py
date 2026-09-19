"""Product-level lifetime contracts (G-02): threads, logging handlers, the log ring, the hub map.

The audit found zero memory instrumentation in the product and the suite. These are the cheap,
deterministic half of the instrumentation: invariants that hold for every repeated call and would
catch a thread or a handler being created per request.
"""

from __future__ import annotations

import logging
import threading


def test_repeated_shell_requests_do_not_add_threads():
    from starlette.testclient import TestClient

    from orderflow_system.dashboard.app import app

    client = TestClient(app)
    assert client.get("/").status_code == 200    # warm any lazy import/thread
    before = threading.active_count()
    for _ in range(5):
        assert client.get("/").status_code == 200
    assert threading.active_count() == before, "a request must not create a thread"


def test_log_install_is_idempotent():
    """install() documents its idempotence; this is the assertion for OUR OWN handlers (pytest
    adds its capture handlers lazily, so the raw root count is not the property)."""
    from orderflow_system.desktop import logs as logs_mod

    def ours() -> int:
        return sum(1 for h in logging.getLogger().handlers
                   if isinstance(h, (logs_mod.BufferHandler,
                                     logging.handlers.RotatingFileHandler)))

    logs_mod.install("INFO")                     # the first call is the one that adds them
    before = ours()
    assert before >= 1
    for _ in range(5):
        logs_mod.install("INFO")
    assert ours() == before, "repeated install() calls add no handlers"


def test_the_log_ring_is_bounded():
    from orderflow_system.desktop import logs as logs_mod

    logger = logging.getLogger("orderflow_system.test_ring")
    for n in range(logs_mod.MAX_LINES * 2):
        logger.info("ring test line %d", n)
    assert len(logs_mod._buffer) <= logs_mod.MAX_LINES, len(logs_mod._buffer)
    assert len(logs_mod.tail(lines=10_000)) <= logs_mod.MAX_LINES


def test_hub_ensure_is_bounded_by_construction():
    from orderflow_system.atlas.hub import FeatureHub

    hub = FeatureHub({})
    for i in range(500):
        hub.ensure(f"SYM{i}")
    assert len(hub.symbols) <= hub.MAX_REST_SYMBOLS
