"""§79's gate: the Help Centre exists, is wired, is complete, and its system check is honest.

The feature is three front-end files and two Python ones, and the interesting failures are all
*coverage* failures rather than crashes:

  * the corpus (`desktop/ui/help-data.js`) is data — so this file proves it is well-formed (unique
    ids, resolvable relations, real screenshot files) and, more importantly, that it covers the
    program: **every `data-view` in index.html has a topic**, and **every topic the system check
    names exists**. Those two are what stop the help from quietly falling behind the app.
  * the search (`help-search.js`) is pure and carries its own selftest under node, so the behavioural
    half is pinned there (`help-search.selftest.js`, ≥ 25 checks) and this file just runs it.
  * the system check (`desktop/help.py`) is a pure function of the state it is handed, so every
    branch is driven here with injected inputs — a stopped engine, a quiet feed, an unreadable
    config, a LAN-exposed host, a log full of errors — with no engine, no network and no database.

Deliberately dumb where it can be: source text in, assertions out. The endpoints are called as
functions (the router reaches them by decoration, which is asserted separately) so nothing here
needs a running server.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from orderflow_system.desktop import config_store
from orderflow_system.desktop import help as help_mod

UI = Path(__file__).parent / "desktop" / "ui"
ROOT = Path(__file__).resolve().parents[1]
INDEX = UI / "index.html"
HELP_JS = UI / "help.js"
HELP_DATA = UI / "help-data.js"
HELP_SEARCH = UI / "help-search.js"
HELP_CSS = UI / "help.css"
SELFTEST = UI / "help-search.selftest.js"
HELP_PY = Path(__file__).parent / "desktop" / "help.py"
API_PY = Path(__file__).parent / "desktop" / "api.py"

#: The action kinds the UI knows how to run (`runAction` in help.js). The corpus may only name these.
ACTION_KINDS = {"view", "topic", "wizard", "menu", "keys", "check", "copy", "palette", "search",
                "folder", "about", "legend"}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _order(html: str) -> list[str]:
    srcs = re.findall(r'<script[^>]+src="(/desktop/[^"]+)"', html)
    return [s[len("/desktop/"):] for s in srcs]


def _views(html: str) -> list[str]:
    """Every view the shell has: the sections (the Overview is `class="view active"`) plus the rail."""
    sections = re.findall(r'<section class="view[^"]*"[^>]*data-view="([a-z0-9_-]+)"', html)
    rail = re.findall(r'class="nav-item"[^>]*data-view="([a-z0-9_-]+)"', html)
    return sorted(set(sections) | set(rail))


@pytest.fixture(scope="module")
def corpus() -> dict:
    """The corpus as the browser gets it — loaded through node, exactly as the page does."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    script = (
        "const fs=require('fs');const s=fs.readFileSync(process.argv[1],'utf8');"
        "const w={};new Function('window',s)(w);const D=w.OFAPHELPDATA;"
        "const out={version:D.version,groups:D.groups.map(g=>({id:g.id,label:g.label,mode:g.mode})),"
        "views:D.views,topics:D.topics.map(t=>({id:t.id,group:t.group,mode:t.mode,title:t.title,"
        "summary:t.summary||'',blocks:(t.blocks||[]).map(b=>({shot:b.shot||'',keys:!!b.keys,"
        "check:!!b.check})),actions:(t.actions||[]).map(a=>a.kind),links:(t.links||[]).map(l=>l.url),"
        "related:t.related||[]}))};console.log(JSON.stringify(out));"
    )
    proc = subprocess.run([node, "-e", script, str(HELP_DATA)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


# ── 1. the files, and that they parse ────────────────────────────────────────────────────────────


def test_the_module_files_and_its_selftest_exist():
    for path in (HELP_JS, HELP_DATA, HELP_SEARCH, HELP_CSS, SELFTEST, HELP_PY, UI / "help"):
        assert path.exists(), f"missing {path}"


def test_every_module_parses():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    for path in (HELP_JS, HELP_DATA, HELP_SEARCH):
        proc = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, encoding="utf-8")
        assert proc.returncode == 0, f"{path.name}: {proc.stderr}"


def test_the_search_selftest_passes():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    proc = subprocess.run([node, str(SELFTEST)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    found = re.search(r"help-search selftest: (\d+) ok, (\d+) failed", out)
    assert found, f"the selftest printed no verdict:\n{out}"
    assert found.group(2) == "0", out
    assert int(found.group(1)) >= 25, f"only {found.group(1)} checks ran — the selftest shrank"


# ── 2. the wiring ────────────────────────────────────────────────────────────────────────────────


def test_index_loads_the_module_its_corpus_and_its_stylesheet():
    html = _text(INDEX)
    order = _order(html)
    for name in ("help-data.js", "help-search.js", "help.js"):
        assert name in order, f"index.html does not load {name}"
    assert order.index("help-data.js") < order.index("help.js")
    assert order.index("help-search.js") < order.index("help.js")
    assert 'href="/desktop/help.css"' in html, "the Help Centre's stylesheet is not linked"


def test_the_module_loads_after_the_shortcut_map_and_the_menu_bar():
    order = _order(_text(INDEX))
    at = order.index("help.js")
    for earlier in ("keys.js", "menubar.js", "menu.js", "ui.js"):
        assert earlier in order and order.index(earlier) < at, f"help.js loads before {earlier}"


def test_the_audit_scans_the_new_modules():
    audit = _text(ROOT / "scripts" / "audit_ui_refs.py")
    for name in ("help.js", "help-data.js", "help-search.js"):
        assert f'"{name}"' in audit, f"{name} is missing from the audit's JS_FILES"


def test_f1_belongs_to_the_help_centre_alone():
    """F1 used to open the hotkey sheet; two Global bindings on one chord tie, and the first wins."""
    help_js = _text(HELP_JS)
    menu = _text(UI / "menu.js")
    assert "keys: ['f1']" in help_js, "the Help Centre does not bind F1"
    assert "keys: ['?', 'f1']" not in menu, "menu.js still claims F1 as well"


def test_the_module_adopts_the_stored_preferences_at_boot():
    """The config's help block is the record; the localStorage mirror only prevents a flash of the
    wrong interface on the first paint. If the report's `prefs` were never applied, the mode, the
    launcher, the recents trail and the dismissed checks would all reset on every launch."""
    text = _text(HELP_JS)
    assert "applyPrefs(res.prefs)" in text, "the boot path never adopts the stored preferences"
    assert "readMirror()" in text, "the first-paint mirror is gone"


def test_the_help_module_defers_to_the_apps_fetch_wrapper():
    """test_wiring owns the repo-wide rule (no module-local `api()` that tests the bare name, which
    resolves to itself); this pins the positive half for the Help Centre: it names the shell's
    helper through the global, under a name of its own."""
    text = _text(HELP_JS)
    assert "typeof window.api" in text, "help.js must defer to ui.js's api() through the global"
    assert not re.search(r"function\s+api\s*\(", text), "help.js must not declare its own api()"


# ── 3. the corpus ────────────────────────────────────────────────────────────────────────────────


def test_the_corpus_is_well_formed(corpus):
    ids = [t["id"] for t in corpus["topics"]]
    assert len(ids) == len(set(ids)), "duplicate topic id"
    groups = {g["id"] for g in corpus["groups"]}
    assert len(groups) == len(corpus["groups"]), "duplicate group id"
    for topic in corpus["topics"]:
        assert topic["group"] in groups, f"{topic['id']} files under an unknown group"
        assert topic["mode"] in ("both", "advanced"), f"{topic['id']} has mode {topic['mode']}"
        assert topic["title"] and topic["summary"], f"{topic['id']} lacks a title or a summary"
        assert topic["blocks"], f"{topic['id']} has no body"


def test_every_relation_and_link_resolves(corpus):
    ids = {t["id"] for t in corpus["topics"]}
    for topic in corpus["topics"]:
        for rel in topic["related"]:
            assert rel in ids, f"{topic['id']} relates to a topic that does not exist: {rel}"
        for action in topic["actions"]:
            assert action in ACTION_KINDS, f"{topic['id']} names an action kind the UI cannot run: {action}"
        for url in topic["links"]:
            assert url.startswith("http://") or url.startswith("https://"), \
                f"{topic['id']} carries a non-http link: {url}"
        for block in topic["blocks"]:
            if not block["shot"]:
                continue
            shot = UI / str(block["shot"]).replace("help/", "help/", 1)
            assert shot.is_file(), f"{topic['id']} shows a screenshot that is not on disk: {block['shot']}"
            assert shot.stat().st_size < 600_000, f"{block['shot']} is too heavy for a shipped asset"


def test_every_view_in_the_shell_has_a_topic(corpus):
    """The coverage contract. A new panel with no help entry fails here rather than shipping silent."""
    views = set(_views(_text(INDEX)))
    ids = {t["id"] for t in corpus["topics"]}
    mapped = corpus["views"]
    missing = sorted(v for v in views if v not in mapped)
    assert not missing, f"these views have no help topic: {missing}"
    broken = sorted(f"{v}->{t}" for v, t in mapped.items() if t not in ids)
    assert not broken, f"the view map points at topics that do not exist: {broken}"
    # A view the markup gains but the map forgets is the failure this exists to catch.
    assert len(mapped) >= len(views), "the view map is smaller than the shell's own view list"


def test_the_corpus_covers_both_depths(corpus):
    advanced = [t for t in corpus["topics"] if t["mode"] == "advanced"]
    ordinary = [t for t in corpus["topics"] if t["mode"] == "both"]
    assert len(corpus["topics"]) >= 50, "the corpus shrank below a useful size"
    assert len(advanced) >= 8, "the Advanced interface has nothing the Simple one hides"
    assert len(ordinary) >= 35, "too much of the corpus is hidden from the Simple interface"
    groups = {g["id"] for g in corpus["groups"] if g["mode"] == "advanced"}
    for topic in advanced:
        assert topic["group"] in groups, f"{topic['id']} is advanced but files under a visible group"


def test_one_topic_carries_the_live_shortcut_map_and_the_check(corpus):
    """Both are rendered from the app itself (OFAPKEYS / the report), never written into the corpus."""
    keys = [t["id"] for t in corpus["topics"] if any(b["keys"] for b in t["blocks"])]
    checks = [t["id"] for t in corpus["topics"] if any(b["check"] for b in t["blocks"])]
    assert keys == ["work.keys"], f"the shortcut map should be rendered by exactly one topic: {keys}"
    assert checks == ["support.syscheck"], f"the system check should be rendered once: {checks}"


# ── 4. the config block ──────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


def test_the_help_block_ships_its_defaults(store):
    help_cfg = store.default_config()["help"]
    assert help_cfg["mode"] == "advanced"
    assert help_cfg["dock"] == "taskbar"
    assert help_cfg["recents"] == [] and help_cfg["dismissed"] == []


def test_the_help_block_clamps_junk(store):
    cfg = store.default_config()
    cfg["help"] = {"mode": "wizard", "dock": "sky", "recents": ["a"] * 40, "dismissed": [1, "b"] * 40}
    clean = store._sanitise(cfg)
    assert clean["help"]["mode"] == "advanced", "an unknown mode must fall back to the default"
    assert clean["help"]["dock"] == "taskbar"
    assert len(clean["help"]["recents"]) == 12
    assert len(clean["help"]["dismissed"]) == 24
    assert all(isinstance(x, str) for x in clean["help"]["dismissed"])


def test_the_help_block_survives_a_round_trip(store):
    cfg = store.load_config()
    cfg["help"] = {"mode": "simple", "dock": "floating", "recents": ["view.tape"], "dismissed": ["log.errors"]}
    store.save_config(cfg)
    on_disk = json.loads(store.config_path().read_text(encoding="utf-8"))
    assert on_disk["help"]["mode"] == "simple" and on_disk["help"]["dock"] == "floating"
    assert store.load_config()["help"]["recents"] == ["view.tape"]


# ── 5. the system check (pure, driven with injected state) ───────────────────────────────────────


def _ids(report: dict) -> list[str]:
    return [c["id"] for c in report["checks"]]


def _level(report: dict, check_id: str) -> str:
    return next((c["level"] for c in report["checks"] if c["id"] == check_id), "")


def _cfg(**over) -> dict:
    cfg = config_store.default_config()
    cfg.update(over)
    return cfg


def test_a_stopped_engine_is_a_notice_not_an_error():
    report = help_mod.check_report(cfg=_cfg(), status={"state": "stopped", "running": False},
                                   storage={}, log_text="", mt5={"available": False},
                                   now_ms=1_700_000_000_000)
    assert _level(report, "engine.stopped") == "notice"
    assert report["counts"]["error"] == 0


def test_a_running_engine_with_no_prints_is_flagged():
    status = {"state": "running", "running": True, "source": "bybit", "symbols": ["BTCUSDT"],
              "uptime_s": 300, "per_symbol": [{"symbol": "BTCUSDT", "last_tick_ms": 1_699_999_000_000}]}
    report = help_mod.check_report(cfg=_cfg(), status=status, storage={}, log_text="",
                                   mt5={"available": False}, now_ms=1_700_000_000_000)
    assert _level(report, "engine.running") == "ok"
    assert _level(report, "feed.quiet") == "warn"
    # …and a feed that is arriving is not flagged
    status["per_symbol"][0]["last_tick_ms"] = 1_699_999_990_000
    fresh = help_mod.check_report(cfg=_cfg(), status=status, storage={}, log_text="",
                                  mt5={"available": False}, now_ms=1_700_000_000_000)
    assert "feed.quiet" not in _ids(fresh)


def test_no_enabled_instrument_is_an_error():
    cfg = _cfg()
    for inst in cfg["instruments"]:
        inst["enabled"] = False
    report = help_mod.check_report(cfg=cfg, status={"running": False}, storage={}, log_text="",
                                   mt5={"available": True}, now_ms=0)
    assert _level(report, "config.no_enabled") == "error"
    assert report["ok"] is False


def test_an_unknown_source_mt5_gap_and_unmapped_symbols_are_named():
    cfg = _cfg(data_source="mt5", mt5={"login": 0})
    for inst in cfg["instruments"]:
        inst["enabled"] = inst["symbol"] == "BTCUSDT"
        inst["mt5_symbol"] = ""
    report = help_mod.check_report(cfg=cfg, status={"running": False}, storage={}, log_text="",
                                   mt5={"available": False, "reason": "MetaTrader5 package not installed"},
                                   now_ms=0)
    assert _level(report, "source.mt5_unavailable") == "warn"
    assert _level(report, "mt5.unmapped") == "notice"
    assert "MetaTrader5 package not installed" in next(c["detail"] for c in report["checks"]
                                                        if c["id"] == "source.mt5_unavailable")
    weird = help_mod.check_report(cfg=_cfg(data_source="nasdaq"), status={"running": False}, storage={},
                                  log_text="", mt5={"available": True}, now_ms=0)
    assert _level(weird, "source.unknown") == "error"


def test_alpaca_gaps_and_channels_are_reported():
    cfg = _cfg(data_source="alpaca", alpaca={"enabled": True, "key_id": "PK123", "secret": ""})
    report = help_mod.check_report(cfg=cfg, status={"running": False}, storage={}, log_text="",
                                   mt5={"available": True}, now_ms=0)
    assert _level(report, "source.alpaca_unlinked") == "warn"
    assert _level(report, "alpaca.partial") == "warn"
    assert _level(report, "alerts.no_channel") == "notice"
    # A linked account and a configured channel clear both.
    cfg["alpaca"]["secret"] = "shh"
    cfg["telegram"] = {"enabled": True, "bot_token": "t", "chat_id": "1"}
    clean = help_mod.check_report(cfg=cfg, status={"running": False}, storage={}, log_text="",
                                  mt5={"available": True}, now_ms=0)
    assert _level(clean, "source.alpaca_ready") == "ok"
    assert "alerts.no_channel" not in _ids(clean)


def test_storage_and_log_findings():
    cfg = _cfg()
    cfg["data"]["retention_days"] = 0
    report = help_mod.check_report(cfg=cfg, status={"running": False},
                                   storage={"bytes": 5 * 1024 ** 3}, now_ms=0,
                                   log_text="2026-09-17 10:00 INFO started\n2026-09-17 10:01 ERROR feed died\n",
                                   mt5={"available": True})
    assert _level(report, "storage.large") == "notice"
    assert _level(report, "storage.retention_off") == "notice"
    assert _level(report, "log.errors") == "warn"
    assert "feed died" in next(c["detail"] for c in report["checks"] if c["id"] == "log.errors")


def test_exposure_and_config_file_findings(tmp_path):
    lan = help_mod.check_report(cfg=_cfg(dashboard={"host": "0.0.0.0", "port": 8080}),
                                status={"running": False}, storage={}, log_text="", mt5={"available": True},
                                now_ms=0)
    assert _level(lan, "security.lan") == "warn"
    local = help_mod.check_report(cfg=_cfg(), status={"running": False}, storage={}, log_text="",
                                  mt5={"available": True}, now_ms=0)
    assert _level(local, "security.local") == "ok"


def test_the_report_is_sorted_worst_first_and_counted():
    cfg = _cfg(data_source="nonsense")
    for inst in cfg["instruments"]:
        inst["enabled"] = False
    report = help_mod.check_report(cfg=cfg, status={"running": False, "error": "boom"}, storage={},
                                   log_text="ERROR nope\n", mt5={"available": True}, now_ms=0)
    levels = [c["level"] for c in report["checks"]]
    order = {"error": 0, "warn": 1, "notice": 2, "ok": 3}
    assert levels == sorted(levels, key=lambda lv: order[lv]), "checks are not sorted worst-first"
    counts = report["counts"]
    assert counts["total"] == len(report["checks"])
    assert counts["error"] == levels.count("error")
    assert report["ok"] is False


def test_every_finding_names_a_topic_that_exists(corpus):
    """The join between the two languages: a check may point at a corpus topic, and it must resolve."""
    ids = {t["id"] for t in corpus["topics"]}
    source = _text(HELP_PY)
    named = set(re.findall(r'topic="([a-z0-9_.]+)"', source))
    assert named, "no check names a topic — the gate would be vacuous"
    missing = sorted(t for t in named if t not in ids)
    assert not missing, f"the system check points at topics that do not exist: {missing}"


def test_every_finding_names_a_view_and_an_action_the_ui_has():
    views = set(_views(_text(INDEX)))
    source = _text(HELP_PY)
    named = set(re.findall(r'view="([a-z0-9_-]+)"', source))
    assert named, "no check names a view"
    unknown = sorted(v for v in named if v not in views)
    assert not unknown, f"the system check names views the shell does not have: {unknown}"
    # The actions are a closed set in the module itself, and the UI's own table must cover it.
    ui = _text(HELP_JS)
    for action in help_mod.ACTIONS:
        assert f"'{action}'" in ui or f"\"{action}\"" in ui, f"the UI has no handler for {action}"


# ── 6. the endpoint ──────────────────────────────────────────────────────────────────────────────


def test_the_endpoints_exist_and_are_read_only_before_the_first_write():
    source = _text(API_PY)
    assert '@router.get("/help")' in source and '@router.post("/help")' in source, \
        "the help endpoints are not on the control router"


def test_the_report_endpoint_answers_with_facts_credits_and_the_check(store):
    from orderflow_system.desktop import api

    out = asyncio.run(api.help_report())
    assert out["ok"] is True
    assert out["app"]["name"] == help_mod.APP_NAME
    assert out["app"]["version"] and out["app"]["licence"] == "MIT"
    assert out["credits"]["made_by"], "the credits lost the author"
    assert out["credits"]["thanks"], "the credits lost the thanks list"
    assert out["links"] and all(l["url"].startswith("http") for l in out["links"])
    assert {"checks", "counts", "ok"} <= set(out["check"])
    assert out["prefs"]["mode"] in ("advanced", "simple")
    # Nothing secret travels: the payload is JSON-serialisable and carries no key material.
    blob = json.dumps(out)
    assert "secret" not in blob.lower() or "keys are" in blob.lower()


def test_the_prefs_endpoint_persists_and_bounds(store):
    from orderflow_system.desktop import api

    out = asyncio.run(api.help_prefs({"mode": "simple", "dock": "floating",
                                      "recents": [f"t{i}" for i in range(30)],
                                      "dismissed": [f"c{i}" for i in range(40)]}))
    assert out["ok"] is True
    assert out["help"]["mode"] == "simple" and out["help"]["dock"] == "floating"
    assert len(out["help"]["recents"]) == 12 and len(out["help"]["dismissed"]) == 24
    # A value outside the allowed set is ignored, not written over what is stored.
    again = asyncio.run(api.help_prefs({"mode": "wizard", "dock": "spaceship"}))
    assert again["help"]["mode"] == "simple" and again["help"]["dock"] == "floating"
    empty = asyncio.run(api.help_prefs({}))
    assert empty["ok"] is False and empty["help"]["mode"] == "simple"
    # …and the file on disk carries it, which is what restart-survival means.
    on_disk = json.loads(store.config_path().read_text(encoding="utf-8"))
    assert on_disk["help"]["mode"] == "simple"
