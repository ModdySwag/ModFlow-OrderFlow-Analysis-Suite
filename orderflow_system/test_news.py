"""The News panel (desktop/ui/news.js) — the app's own headlines, read from the app's own endpoint.

The panel's gate is a countable claim: every headline the user sees comes back from
`GET /api/atlas/context/{symbol}` in the shape the server actually sends, and when there is nothing to
show the panel says which of the five reasons it is instead of going blank. The deciding half is pure,
so it is pinned in Node (`news.selftest.js`) against a payload captured from a live sandbox instance;
this file gates the invariants around it: the module is loaded and registered with the UI audit, the
field names it parses are the ones the endpoint publishes (`title`/`link`/`source`/`published_ms`), the
feed URL is only ever read from the config key `context.news_url` — never invented — and the panel
stores nothing, holds one timer, and never reaches for the engine or a data stream.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).parent / "desktop" / "ui"
NEWS = UI / "news.js"
SELFTEST = UI / "news.selftest.js"
ROOT = Path(__file__).resolve().parents[1]

#: The config key a custom feed lives under (desktop/config_store.py, the "context" block).
FEED_KEY = "context.news_url"


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_the_news_files_exist():
    assert NEWS.is_file(), "desktop/ui/news.js is missing"
    assert SELFTEST.is_file(), "desktop/ui/news.selftest.js is missing"


def test_the_news_module_parses_as_javascript():
    proc = subprocess.run([_node(), "--check", str(NEWS)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr


def test_the_news_selftest_passes():
    proc = subprocess.run([_node(), str(SELFTEST)], capture_output=True, text=True, timeout=180,
                          cwd=str(ROOT))
    out = proc.stdout.strip()
    match = re.search(r"news selftest: (\d+) ok, (\d+) failed", out)
    assert match, f"unexpected selftest output: {out!r}\n{proc.stderr}"
    ok, failed = int(match.group(1)), int(match.group(2))
    assert failed == 0, out
    assert ok >= 6, f"the self-test shrank to {ok} checks — expected the parsing and state coverage"
    assert proc.returncode == 0


def test_the_news_module_exposes_the_documented_surface():
    src = _read(NEWS)
    assert "window.OFAPNEWS" in src
    for name in ("refresh", "paint", "plan", "items", "item", "row", "relTime", "hostOf",
                 "fullTime", "limitOf", "activeSymbol", "state", "FEED_KEY", "LIMIT_MAX"):
        assert name in src, f"news.js must expose {name}"


def test_the_news_module_is_loaded_and_registered():
    html = _read(UI / "index.html")
    assert 'src="/desktop/news.js"' in html, "index.html must load the news panel"
    assert 'data-view="news"' in html, "and the view section it watches"
    assert "news.js" in _read(ROOT / "scripts" / "audit_ui_refs.py"), "register it in JS_FILES"
    assert html.index('src="/desktop/ui.js"') < html.index('src="/desktop/news.js"'), \
        "the panel reads S and api(), so it loads after the controller"


def test_the_news_module_reads_the_real_payload_fields():
    """The parser must reference the fields the endpoint actually sends — a rename there leaves the
    panel rendering empty rows with no error anywhere."""
    src = _read(NEWS)
    for field in ("payload.news", "raw.title", "raw.link", "raw.source", "raw.published_ms"):
        assert field in src, f"news.js does not read {field}"
    assert "'/api/atlas/context/'" in src or "/api/atlas/context/" in src, "the endpoint it calls"
    assert "news_limit" in src, "the Query parameter the endpoint takes"
    assert "stats" in src and "feeds" in src, \
        "stats.feeds is how the server reports the feeds it is using when no custom one is set"


def test_the_feed_url_is_only_ever_read_from_the_config():
    """Never invent the user's feed: the module must name the config key, and no line of CODE may
    carry a feed URL of its own (prose may quote one to explain a rule)."""
    src = _read(NEWS)
    assert FEED_KEY in src, f"the panel must name {FEED_KEY} where it explains the source"
    assert "cfg.context" in src or ".context" in src, "the feed URL is read from the context block"
    code = re.sub(r"/\*[\s\S]*?\*/", "", src)             # comments are prose, not behaviour
    assert not re.search(r"https?://[a-z0-9.-]+\.[a-z]{2,}", code), \
        "news.js must not embed a feed URL — the feed comes from the config"


def test_every_empty_state_has_a_sentence_naming_the_setting_that_fixes_it():
    src = _read(NEWS)
    for state in ("nosymbol", "error", "disabled", "off", "empty", "unconfigured", "loading"):
        assert f"'{state}'" in src, f"the {state} state must exist"
    assert "'not configured'" in src, "and the honest label for a panel with no source at all"
    assert "context.enabled" in src and "context.news" in src, \
        "the two switches that hide the headlines must be named as the config stores them"


def test_the_news_module_stores_nothing_and_never_reaches_for_ingest():
    src = _read(NEWS)
    for forbidden in ("localStorage", "sessionStorage", "indexedDB", "WebSocket", "EventSource",
                      "/api/control/engine", "engine/start", "engine/stop", "OFAPBUS"):
        assert forbidden not in src, f"news.js must not touch {forbidden}"
    assert src.count("setInterval(") == 1, "one timer for the panel, guarded by the visible section"


def test_the_news_panel_boots_like_every_other_view_module():
    """Self-registering and watching its own section: a nav hook misses activation from a hash link or
    a restored session, and the panel must fetch again when its symbol moves underneath it."""
    src = _read(NEWS)
    assert "MutationObserver" in src and "attributeFilter: ['class']" in src
    assert "classList.contains('active')" in src, "it only works while the section is on screen"
    assert "symbolSelect" in src, "the symbol is read from the app's own instrument select"
    assert "typeof S !== 'undefined'" in src, "read defensively: the engine state may not be there yet"
    assert 'target="_blank"' in src and "noopener" in src, "an external link opens out, not in place"


def test_the_endpoint_the_panel_calls_exists():
    """The path is written as a literal so scripts/audit_ui_refs.py can see it; this is the other half."""
    api_src = _read(ROOT / "orderflow_system" / "atlas" / "api.py")
    assert '@router.get("/context/{symbol}")' in api_src, "the route the panel depends on"
    assert "news_url" in api_src and "news_limit" in api_src, "and the parameters it sends"
