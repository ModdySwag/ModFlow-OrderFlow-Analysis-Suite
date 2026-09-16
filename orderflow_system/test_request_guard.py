"""The local-request guard (secure2 sweep): the loopback API answers only loopback clients.

The control API is unauthenticated by design — it is a single-user desktop app on
127.0.0.1 and the UI is its only legitimate client. Two browser-native attacks on that
shape are cheap to close without touching any endpoint:

* **DNS rebinding.** A name an attacker controls resolves to 127.0.0.1; the attacker's
  script is then *same-origin* with this API and can read anything a GET returns —
  including /api/control/config, which carries the Alpaca key and the Telegram token.
  A Host allowlist (loopback names only) refuses the rebinding name.
* **Cross-site request forgery.** Body-less mutating POSTs (config/reset, engine/stop,
  logs/clear, storage/prune, alerts/clear, replay stop …) are "simple requests": a page
  the user visits can fire them without a preflight and the action happens even though
  the page cannot read the reply. Mutating requests must therefore either carry no
  browser Origin (native clients, curl, the test client) or a loopback one, and never
  declare `Sec-Fetch-Site: cross-site`.

These tests are the receipt that the guard refuses the two attack shapes AND that every
first-party shape still works: loopback Hosts (127.0.0.1, localhost, the test client's
own name), same-origin POSTs, and native POSTs with no Origin at all.
"""

from __future__ import annotations


def _client(**kwargs):
    from fastapi.testclient import TestClient

    # build_app() may run once per process; test_wiring owns the shared singleton
    from orderflow_system.test_wiring import _desktop_app

    return TestClient(_desktop_app(), **kwargs)


def test_the_shipped_dashboard_default_is_loopback():
    """The standalone pipeline (`python -m orderflow_system.main`) starts uvicorn from
    DashboardConfig — a `0.0.0.0` default would offer an unauthenticated trading terminal to
    the whole LAN (the repo's own feasibility notes called this out). Loopback is the shipped
    default; anyone who wants LAN access sets the host explicitly."""
    from orderflow_system.config import settings as st

    assert st.DASHBOARD.host in ("127.0.0.1", "localhost", "::1"), st.DASHBOARD.host


# The one mutating route with no side effect at all: an unknown parameter path is
# rejected by the registry before anything is written. Perfect guard probe.
_PROBE_PATH = "/api/control/params"
_PROBE_BODY = {"path": "secure2.probe.not.a.real.param", "value": 1}


def test_a_rebinding_host_header_is_refused():
    """Host: evil.example (what a rebinding fetch sends) must not reach the API."""
    client = _client(base_url="http://evil.example")
    assert client.get("/healthz").status_code == 403
    res = client.get("/api/control/bootstrap")
    assert res.status_code == 403, "the config payload must be unreachable through a rebinding name"
    assert "Moddy" not in res.text  # no data of any kind leaks, only the refusal


def test_loopback_hosts_keep_answering():
    """The app's own addresses — and the test client's — must be untouched."""
    for base in ("http://127.0.0.1:8099", "http://localhost:8099", "http://testserver"):
        client = _client(base_url=base)
        assert client.get("/healthz").status_code == 200, base
        assert client.get("/api/control/bootstrap").status_code == 200, base


def test_cross_origin_mutations_are_refused():
    """A browser page from another origin cannot fire a state-changing POST."""
    client = _client()
    res = client.post(_PROBE_PATH, json=_PROBE_BODY, headers={"Origin": "https://evil.example"})
    assert res.status_code == 403, "cross-origin POST must be refused"
    res = client.post(_PROBE_PATH, json=_PROBE_BODY,
                      headers={"Sec-Fetch-Site": "cross-site"})
    assert res.status_code == 403, "a cross-site declared POST must be refused"
    # reads stay open: a cross-origin GET is harmless (the browser cannot read the reply)
    assert client.get("/healthz", headers={"Origin": "https://evil.example"}).status_code == 200


def test_first_party_mutations_still_work():
    """Same-origin POSTs (the real UI) and native POSTs (no Origin) are unaffected."""
    client = _client()
    same_origin = client.post(_PROBE_PATH, json=_PROBE_BODY,
                              headers={"Origin": "http://127.0.0.1:8099"})
    assert same_origin.status_code == 200, same_origin.text
    assert same_origin.json().get("ok") is False  # the registry refused the unknown path, as before
    native = client.post(_PROBE_PATH, json=_PROBE_BODY)
    assert native.status_code == 200, native.text
    for base in ("http://127.0.0.1:8099", "http://localhost:8099", "http://testserver"):
        res = _client(base_url=base).post(_PROBE_PATH, json=_PROBE_BODY,
                                          headers={"Origin": base})
        assert res.status_code == 200, (base, res.status_code)


def _ws_refusal(client, **kwargs):
    """True when the websocket handshake was refused before any message could flow.

    Written so it terminates in BOTH states: against a guarded server the handshake (or the
    first receive) raises; against an unguarded one the ping is answered and the helper
    reports "not refused" instead of blocking on a stream that may legitimately be silent.
    """
    try:
        with client.websocket_connect("/ws", **kwargs) as ws:
            ws.send_text("ping")
            ws.receive_json()
        return False                  # the server accepted and answered — not refused
    except Exception:
        return True


def test_a_cross_origin_websocket_handshake_is_refused():
    """A wrong-Origin page must not be able to open the live stream."""
    client = _client()
    assert _ws_refusal(client, headers={"origin": "https://evil.example"}), \
        "a cross-origin websocket was accepted"
    assert _ws_refusal(client, headers={"sec-fetch-site": "cross-site"}), \
        "a cross-site declared websocket was accepted"


def test_the_apps_own_websocket_handshake_is_untouched():
    """No Origin (native clients, the test client) and the loopback origin keep working."""
    client = _client()
    with client.websocket_connect("/ws") as ws:
        ws.send_text("ping")
        assert ws.receive_json()["channel"] == "pong"
    with client.websocket_connect("/ws", headers={"origin": "http://127.0.0.1:8099"}) as ws:
        ws.send_text("ping")
        assert ws.receive_json()["channel"] == "pong"
