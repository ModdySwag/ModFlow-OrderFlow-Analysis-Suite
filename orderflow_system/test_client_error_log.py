"""The client-error sink stays ONE line per report (secure2 sweep).

`POST /api/control/client-error` exists because a frozen build has no console: the browser's
uncaught errors land in the server log where log tooling can read them. The endpoint already
folded the stack, but the message and the numeric fields were stored raw — an embedded CR/LF
(trivially written by any script in the page) forges whole log lines, complete with fake
timestamps and levels, in the very file used for debugging. Folding every field keeps the
content and loses only the line breaks.
"""

from __future__ import annotations


def test_a_client_error_cannot_forge_extra_log_lines(monkeypatch):
    from fastapi.testclient import TestClient

    from orderflow_system.desktop import api as api_mod
    from orderflow_system.test_wiring import _desktop_app

    calls: list[tuple] = []

    class Capture:
        def error(self, *args, **kwargs):
            calls.append((args, kwargs))

    monkeypatch.setattr(api_mod, "logger", Capture())

    client = TestClient(_desktop_app())
    res = client.post("/api/control/client-error", json={
        "message": "boom\n2026-01-01 00:00:00 [ERROR] orderflow_system.fake: forged line",
        "stack": "at a\nat b",
        "source": "chart.js", "line": {"evil": "x\ny"}, "col": "3\r4",
    })
    assert res.status_code == 200
    assert len(calls) == 1, "one report, one log call"
    args = calls[0][0]
    for value in args:
        assert "\n" not in str(value) and "\r" not in str(value), f"raw CR/LF survived: {value!r}"
    assert "forged line" in str(args[1]), "the content must survive; only the breaks are folded"
    assert "chart.js" in str(args[2])
