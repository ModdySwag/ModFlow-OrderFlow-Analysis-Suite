"""Profiles — switchable playbooks (the `profiles` block in the config store).

One module for the whole profile lifecycle because the same capture/diff/apply logic is needed
by three callers and must not drift between them: the control routes (`api.py`), the boot-time
auto-apply (`launcher.main`), and the tests.

What a profile IS: a named bundle of the analysis blocks in `config_store.PROFILE_BLOCKS` —
feed + instruments, atlas/ofx/studies parameters, UI + layout + workspaces, watchlist, risk,
audio, calendar. What it can NEVER carry: credentials (telegram/notify/platforms/alpaca/mt5),
machine paths, network settings. That is enforced at capture time (the whitelist is the only
thing `profile_capture` reads), so an exported profile is shareable by construction and an
import cannot smuggle a token in.

Apply semantics: the carried blocks are REPLACED wholesale (a switch makes those blocks look
exactly like the profile — `save_config`, not `merge_config`), and the write still passes
through the store's sanitiser, which remains the authority on what actually lands. Blocks the
profile does not carry are untouched. Feed/instruments/atlas/ofx are flagged as "takes effect
on the next engine start" — the same wording the settings view already uses — so a switch is
never mistaken for a live re-tune of a running engine.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from orderflow_system.desktop import config_store

logger = logging.getLogger("orderflow_system.desktop.profiles")

#: Re-exported so routes and tests name the same whitelist the store enforces.
BLOCKS = config_store.PROFILE_BLOCKS
RESTART_BLOCKS = config_store.PROFILE_RESTART_BLOCKS


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id() -> str:
    return "pf" + uuid.uuid4().hex[:8]


def _block(cfg: dict[str, Any]) -> dict[str, Any]:
    block = cfg.get("profiles")
    if not isinstance(block, dict):
        block = {}
        cfg["profiles"] = block
    items = block.get("items")
    if not isinstance(items, dict):
        block["items"] = items = {}
    rules = block.get("rules")
    if not isinstance(rules, dict):
        block["rules"] = rules = {"enabled": False, "sources": {}, "windows": []}
    versions = block.get("versions")
    if not isinstance(versions, dict):
        block["versions"] = versions = {}
    return block


def _same(a: Any, b: Any) -> bool:
    """Deep equality for snapshot data (JSON-safe values only; key order is not identity)."""
    if type(a) is not type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    try:
        return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    except (TypeError, ValueError):
        return False


def changed_blocks(snapshot: dict[str, Any], live: dict[str, Any]) -> list[str]:
    """Which of the snapshot's blocks differ from the live config (the dirty set)."""
    return [key for key, value in snapshot.items() if key in BLOCKS and not _same(live.get(key), value)]


def engine_running() -> bool:
    """Is the engine up? The engine module is optional in unit contexts — that is not an error."""
    from orderflow_system.desktop import engine as engine_mod

    try:
        return bool(engine_mod.engine.status().get("running"))
    except Exception:
        return False


def note_engine_start(cfg: dict[str, Any] | None = None) -> None:
    """The engine has just read everything it consumes, so any standing hold is over.

    Called from EngineController.start() — the one moment that sentence is true, and the only way
    a "restart to apply" note clears. A note can therefore never outlive the restart that answers
    it, and nothing has to remember to clear it.
    """
    stored = config_store.load_config()
    block = stored.get("profiles")
    if isinstance(block, dict) and block.pop("pending_restart", None) is not None:
        config_store.save_config(stored)


def pending_restart(cfg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """What a switch could not land because the engine was already running — None when nothing is.

    Recorded at the moment of the switch (where the store knows exactly which blocks changed and
    that they are engine-read), not inferred later from a config diff: the atlas and ofx blocks are
    re-persisted by their own panels during ordinary use, so a diff would report the app's own
    writes as if the user had changed something. Cleared by the next engine start. `carried` says
    which of the waiting blocks the active playbook carries, so the panel can speak about the
    playbook while the status bar speaks about the engine.
    """
    if not engine_running():
        return None
    cfg = cfg if isinstance(cfg, dict) else config_store.load_config()
    block = cfg.get("profiles") if isinstance(cfg.get("profiles"), dict) else {}
    hold = block.get("pending_restart") if isinstance(block.get("pending_restart"), dict) else {}
    blocks = [key for key in (hold.get("blocks") or []) if key in RESTART_BLOCKS]
    if not blocks:
        return None
    ident = block.get("active") or ""
    entry = (block.get("items") or {}).get(ident) if ident else None
    entry = entry if isinstance(entry, dict) else {}
    return {
        "at": int(hold.get("at") or 0),
        "blocks": blocks,
        "profile": str(hold.get("profile") or ident),
        "name": str(entry.get("name") or hold.get("name") or ident or ""),
        "carried": [key for key in blocks if key in (entry.get("blocks") or [])],
    }


def _free_name(items: dict[str, Any], base: str) -> str:
    taken = {str(x.get("name")) for x in items.values() if isinstance(x, dict)}
    name, n = base, 2
    while name in taken and n < 100:
        name, n = f"{base} {n}", n + 1
    return name[:config_store.PROFILE_NAME_MAX]


def _switch(block: dict[str, Any], ident: str, now: int, *, count: bool) -> None:
    """Point `active` at `ident`: bank the previous playbook's clock and bump the counters.

    `count=True` is a real switch (apply/boot) — `stats.applied` increments. `count=False` is a
    save: the new profile simply IS the current setup, so its clock starts but "applied" (which
    counts switches) does not.
    """
    previous = block.get("active") or ""
    if previous and previous in block["items"] and previous != ident:
        prev_stats = block["items"][previous].setdefault("stats", {})
        since = int(prev_stats.get("active_since") or 0)
        if since:
            prev_stats["active_ms"] = int(prev_stats.get("active_ms") or 0) + max(0, now - since)
        prev_stats["active_since"] = 0
    stats = block["items"][ident].setdefault("stats", {})
    if count:
        stats["applied"] = int(stats.get("applied") or 0) + 1
        stats["last_applied"] = now
    if not int(stats.get("active_since") or 0):
        stats["active_since"] = now
    block["active"] = ident


def _push_version(block: dict[str, Any], ident: str, entry: dict[str, Any]) -> None:
    """Keep the profile as it was before this write — newest first, capped (the layouts' T2 idea)."""
    ring = block["versions"].get(ident)
    if not isinstance(ring, list):
        ring = block["versions"][ident] = []
    ring.insert(0, {"at": now_ms(), "name": str(entry.get("name") or ident)[:config_store.PROFILE_NAME_MAX],
                    "entry": json.loads(json.dumps(entry))})
    del ring[config_store.PROFILE_VERSIONS_MAX:]


def state(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Everything the Profiles view renders, derived from the store's accepted state."""
    cfg = cfg if isinstance(cfg, dict) else config_store.load_config()
    block = cfg.get("profiles") if isinstance(cfg.get("profiles"), dict) else {}
    items_in = block.get("items") if isinstance(block.get("items"), dict) else {}
    active = block.get("active") or ""
    items: list[dict[str, Any]] = []
    now = now_ms()
    for ident, entry in sorted(items_in.items(), key=lambda kv: (kv[1].get("created") or 0)):
        stats = dict(entry.get("stats") or {})
        elapsed = now - int(stats.get("active_since") or 0) if ident == active and stats.get("active_since") else 0
        items.append({
            "id": ident,
            "name": entry.get("name") or ident,
            "description": entry.get("description") or "",
            "tags": list(entry.get("tags") or []),
            "created": entry.get("created") or 0,
            "updated": entry.get("updated") or 0,
            "blocks": list(entry.get("blocks") or []),
            "block_count": len(entry.get("blocks") or []),
            "stats": {
                "applied": int(stats.get("applied") or 0),
                "last_applied": int(stats.get("last_applied") or 0),
                "active_ms": int(stats.get("active_ms") or 0) + max(0, elapsed),
            },
            "dirty": ident == active and bool(changed_blocks(entry.get("snapshot") or {}, cfg)),
            "dirty_blocks": changed_blocks(entry.get("snapshot") or {}, cfg) if ident == active else [],
            # The version ring the store already keeps (update/rename/restore bank one each), exposed
            # so the view can offer the recovery the delete copy has always promised. Trimmed to what
            # a row renders: when it was banked, the name it had, and which blocks it carried.
            "versions": [
                {"at": int(v.get("at") or 0), "name": str(v.get("name") or ""),
                 "blocks": list((v.get("entry") or {}).get("blocks") or [])}
                for v in (block.get("versions") or {}).get(ident) or []
            ][:config_store.PROFILE_VERSIONS_MAX],
        })
    return {
        "ok": True,
        "active": active,
        "default": block.get("default") or "",
        "auto_apply": bool(block.get("auto_apply")),
        "rules": block.get("rules") or {"enabled": False, "sources": {}, "windows": []},
        "items": items,
        "count": len(items),
        "blocks_available": list(BLOCKS),
        "restart_blocks": list(RESTART_BLOCKS),
        # What the running engine has not picked up yet (None when it is up to date) — the panel
        # and the status bar read the same derived answer.
        "pending_restart": pending_restart(cfg),
        "note": "profiles live in your config file and never carry credentials or machine paths",
    }


def save(name: str, description: str = "", tags: "list[str] | None" = None,
         blocks: "list[str] | None" = None, from_defaults: bool = False) -> dict[str, Any]:
    """Create a profile from the live setup (or from factory defaults), returning fresh state.

    The new profile becomes the ACTIVE playbook — it is, by definition, what you are running
    right now — so its clock starts and any later change to a carried block shows up as drift
    ("Update from current"). `applied` counts switches, not saves, so it starts at 0.
    """
    name = str(name or "").strip()
    if not name:
        return {**state(), "ok": False, "error": "a profile needs a name"}
    cfg = config_store.load_config()
    block = _block(cfg)
    if len(block["items"]) >= config_store.PROFILE_ITEMS_MAX:
        return {**state(cfg), "ok": False,
                "error": f"the store holds {config_store.PROFILE_ITEMS_MAX} profiles already"}
    source = config_store.default_config() if from_defaults else cfg
    snapshot = config_store.profile_capture(source, tuple(blocks) if blocks else None)
    if not snapshot:
        return {**state(cfg), "ok": False,
                "error": "nothing to capture — the chosen blocks are not in the config"}
    ident = new_id()
    block["items"][ident] = {
        "id": ident,
        "name": name,
        "description": str(description or "").strip(),
        "tags": [str(t).strip() for t in (tags or []) if str(t).strip()],
        "created": now_ms(),
        "updated": now_ms(),
        "blocks": list(snapshot),
        "snapshot": snapshot,
        "stats": {"applied": 0, "last_applied": 0, "active_ms": 0, "active_since": 0},
    }
    _switch(block, ident, now_ms(), count=False)
    saved = config_store.save_config(cfg)
    out = state(saved)
    if ident not in {row["id"] for row in out["items"]}:
        return {**out, "ok": False, "error": "the store refused this profile (name or snapshot shape)"}
    logger.info("profile saved: %s (%s)", name, ident)
    return {**out, "saved": ident}


def preview(profile_id: str) -> dict[str, Any]:
    """What applying this profile would change, without writing anything."""
    cfg = config_store.load_config()
    block = cfg.get("profiles") or {}
    entry = (block.get("items") or {}).get(str(profile_id or "").strip().lower())
    if not isinstance(entry, dict):
        return {**state(cfg), "ok": False, "error": f"no profile with id {profile_id!r}"}
    snapshot = entry.get("snapshot") or {}
    changed = changed_blocks(snapshot, cfg)
    return {
        "ok": True,
        "id": entry.get("id"),
        "name": entry.get("name"),
        "changed": changed,
        "unchanged": [key for key in snapshot if key not in changed],
        "restart": [key for key in changed if key in RESTART_BLOCKS],
        "already_current": not changed,
        **_state_minus_items(cfg),
    }


def _state_minus_items(cfg: dict[str, Any]) -> dict[str, Any]:
    full = state(cfg)
    return {k: v for k, v in full.items() if k not in ("items", "note", "ok")}


def apply(profile_id: str, *, dry_run: bool = False, touch_stats: bool = True) -> dict[str, Any]:
    """Switch to a profile: replace its carried blocks, update the active pointer and the clock.

    The previous profile's session is banked into `stats.active_ms` first, so "time under this
    playbook" stays honest across every switch — including the boot-time auto-apply.
    """
    cfg = config_store.load_config()
    block = _block(cfg)
    ident = str(profile_id or "").strip().lower()
    entry = block["items"].get(ident)
    if not isinstance(entry, dict):
        return {**state(cfg), "ok": False, "error": f"no profile with id {profile_id!r}"}
    snapshot = entry.get("snapshot") or {}
    changed = changed_blocks(snapshot, cfg)
    result: dict[str, Any] = {
        "ok": True,
        "id": ident,
        "name": entry.get("name"),
        "changed": changed,
        "unchanged": [key for key in snapshot if key not in changed],
        "restart": [key for key in changed if key in RESTART_BLOCKS],
    }
    if dry_run:
        return {**result, "dry_run": True, "already_current": not changed, **_state_minus_items(cfg)}

    now = now_ms()
    if touch_stats:
        _switch(block, ident, now, count=True)

    for key, value in snapshot.items():                    # replace, not merge: a switch is a switch
        if key in BLOCKS:
            cfg[key] = json.loads(json.dumps(value))
    # The running engine cannot be re-tuned from here: record exactly what this switch changed
    # that it reads at start, so the notice names real blocks. A switch that lands everything it
    # carries clears any earlier hold instead.
    restart = [key for key in changed if key in RESTART_BLOCKS]
    if restart and engine_running():
        block["pending_restart"] = {"at": now, "blocks": restart, "profile": ident,
                                    "name": entry.get("name")}
    else:
        block.pop("pending_restart", None)
    saved = config_store.save_config(cfg)
    logger.info("profile applied: %s (%s) — %d block(s) changed", entry.get("name"), ident, len(changed))
    return {**result, "applied": True, "already_current": not changed, **state(saved)}


def update(profile_id: str) -> dict[str, Any]:
    """Re-capture a profile from the current setup (modify), banking the old snapshot first."""
    cfg = config_store.load_config()
    block = _block(cfg)
    ident = str(profile_id or "").strip().lower()
    entry = block["items"].get(ident)
    if not isinstance(entry, dict):
        return {**state(cfg), "ok": False, "error": f"no profile with id {profile_id!r}"}
    _push_version(block, ident, entry)
    entry["snapshot"] = config_store.profile_capture(cfg, tuple(entry.get("blocks") or None))
    entry["blocks"] = list(entry["snapshot"])
    entry["updated"] = now_ms()
    saved = config_store.save_config(cfg)
    logger.info("profile updated from current setup: %s", entry.get("name"))
    return {**state(saved), "updated": ident}


def rename(profile_id: str, name: str) -> dict[str, Any]:
    cfg = config_store.load_config()
    block = _block(cfg)
    ident = str(profile_id or "").strip().lower()
    entry = block["items"].get(ident)
    if not isinstance(entry, dict):
        return {**state(cfg), "ok": False, "error": f"no profile with id {profile_id!r}"}
    new_name = str(name or "").strip()[:config_store.PROFILE_NAME_MAX]
    if not new_name:
        return {**state(cfg), "ok": False, "error": "a profile needs a name"}
    entry["name"] = new_name
    entry["updated"] = now_ms()
    return {**state(config_store.save_config(cfg)), "renamed": ident}


def duplicate(profile_id: str, name: str = "") -> dict[str, Any]:
    cfg = config_store.load_config()
    block = _block(cfg)
    ident = str(profile_id or "").strip().lower()
    origin = block["items"].get(ident)
    if not isinstance(origin, dict):
        return {**state(cfg), "ok": False, "error": f"no profile with id {profile_id!r}"}
    if len(block["items"]) >= config_store.PROFILE_ITEMS_MAX:
        return {**state(cfg), "ok": False, "error": "the store is full"}
    copy = json.loads(json.dumps(origin))
    copy["id"] = new_id()
    copy["name"] = _free_name(block["items"], (str(name or "").strip() or f"{origin.get('name') or 'Profile'} copy")
                              [:config_store.PROFILE_NAME_MAX])
    copy["created"] = copy["updated"] = now_ms()
    copy["stats"] = {"applied": 0, "last_applied": 0, "active_ms": 0, "active_since": 0}
    block["items"][copy["id"]] = copy
    return {**state(config_store.save_config(cfg)), "duplicated": copy["id"]}


def delete(profile_id: str) -> dict[str, Any]:
    """Delete a profile. The version ring is kept — that is what makes a delete recoverable."""
    cfg = config_store.load_config()
    block = _block(cfg)
    ident = str(profile_id or "").strip().lower()
    entry = block["items"].get(ident)
    if not isinstance(entry, dict):
        return {**state(cfg), "ok": False, "error": f"no profile with id {profile_id!r}"}
    _push_version(block, ident, entry)
    block["items"].pop(ident, None)
    if block.get("active") == ident:
        block["active"] = ""
    if block.get("default") == ident:
        block["default"] = ""
    saved = config_store.save_config(cfg)                   # the sanitiser drops rules that named it
    logger.info("profile deleted: %s (%s)", entry.get("name"), ident)
    return {**state(saved), "deleted": ident}


def restore_version(profile_id: str, at: int) -> dict[str, Any]:
    """Bring back a previous setup of a profile (an edit or a delete), by its version stamp."""
    cfg = config_store.load_config()
    block = _block(cfg)
    ident = str(profile_id or "").strip().lower()
    ring = block["versions"].get(ident)
    hit = next((row for row in ring if isinstance(row, dict) and int(row.get("at") or 0) == int(at or 0)), None) \
        if isinstance(ring, list) else None
    if not isinstance(hit, dict) or not isinstance(hit.get("entry"), dict):
        return {**state(cfg), "ok": False, "error": f"no version of {profile_id!r} at {at}"}
    restored = json.loads(json.dumps(hit["entry"]))
    restored["id"] = ident
    block["items"][ident] = restored
    saved = config_store.save_config(cfg)
    return {**state(saved), "restored": ident, "restored_at": int(at or 0)}


def set_default(profile_id: str = "", auto_apply: "bool | None" = None) -> dict[str, Any]:
    """Name the profile applied at launch (or "" for none) and optionally flip auto-apply."""
    cfg = config_store.load_config()
    block = _block(cfg)
    ident = str(profile_id or "").strip().lower()
    if ident and ident not in block["items"]:
        return {**state(cfg), "ok": False, "error": f"no profile with id {profile_id!r}"}
    block["default"] = ident
    if auto_apply is not None:
        block["auto_apply"] = bool(auto_apply)
    return {**state(config_store.save_config(cfg)), "default": ident}


def set_rules(rules: dict[str, Any] | None = None, *, enabled: "bool | None" = None) -> dict[str, Any]:
    """Replace the auto-switch rules (or just flip the master switch).

    Rules are stored here, evaluated client-side (the app's clock, the app's view of the feed) and
    applied through the same `apply()` path as a manual switch, so there is exactly one writer.
    """
    cfg = config_store.load_config()
    block = _block(cfg)
    if isinstance(rules, dict):
        block["rules"] = {
            "enabled": bool(rules.get("enabled", block["rules"].get("enabled"))),
            "sources": rules.get("sources") if isinstance(rules.get("sources"), dict) else block["rules"].get("sources"),
            "windows": rules.get("windows") if isinstance(rules.get("windows"), list) else block["rules"].get("windows"),
        }
    if enabled is not None:
        block["rules"]["enabled"] = bool(enabled)
    return state(config_store.save_config(cfg))


def export_bundle(profile_id: str) -> tuple[str, str, str]:
    """(filename, text, error) — a shareable bundle. Stats are history, not setup: not exported."""
    cfg = config_store.load_config()
    block = cfg.get("profiles") or {}
    entry = (block.get("items") or {}).get(str(profile_id or "").strip().lower())
    if not isinstance(entry, dict):
        return "", "", f"no profile with id {profile_id!r}"
    import re

    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(entry.get("name") or entry.get("id")))[:60] or entry["id"]
    bundle = {
        "ofap_profile": 1,
        "exported": now_ms(),
        "profile": {
            "name": entry.get("name"),
            "description": entry.get("description") or "",
            "tags": list(entry.get("tags") or []),
            "blocks": list(entry.get("blocks") or []),
            "snapshot": entry.get("snapshot") or {},
        },
    }
    return f"profile-{safe}.json", json.dumps(bundle, indent=2), ""


def import_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Take a bundle (scraped from a file another user exported) and store it as a new profile."""
    cfg = config_store.load_config()
    block = _block(cfg)
    if len(block["items"]) >= config_store.PROFILE_ITEMS_MAX:
        return {**state(cfg), "ok": False, "error": "the store is full"}
    data = bundle.get("profile") if isinstance(bundle.get("profile"), dict) else bundle
    if not isinstance(data, dict) or not isinstance(data.get("snapshot"), dict):
        return {**state(cfg), "ok": False, "error": "this file does not carry a profile"}
    ident = new_id()
    block["items"][ident] = {
        "id": ident,
        "name": _free_name(block["items"], str(data.get("name") or "Imported profile")
                           [:config_store.PROFILE_NAME_MAX]),
        "description": str(data.get("description") or ""),
        "tags": [str(t) for t in (data.get("tags") or []) if str(t).strip()],
        "created": now_ms(),
        "updated": now_ms(),
        "blocks": [],
        "snapshot": data.get("snapshot") or {},
        "stats": {"applied": 0, "last_applied": 0, "active_ms": 0, "active_since": 0},
    }
    saved = config_store.save_config(cfg)
    out = state(saved)
    if ident not in {row["id"] for row in out["items"]}:
        return {**out, "ok": False, "error": "the store refused this bundle (snapshot shape or size)"}
    logger.info("profile imported: %s (%s)", block["items"][ident]["name"], ident)
    return {**out, "imported": ident}


def boot_apply() -> str | None:
    """Apply the default profile at launch when auto-apply is on. Returns the id applied, or None.

    Called by `launcher.main` before the app is built, so the first `/bootstrap` a UI sees already
    reflects the profile — there is no window where the app serves a setup the user did not pick.
    """
    cfg = config_store.load_config()
    block = cfg.get("profiles") if isinstance(cfg.get("profiles"), dict) else {}
    if not block.get("auto_apply") or not block.get("default"):
        return None
    result = apply(block["default"])
    if result.get("ok"):
        logger.info("startup profile applied: %s — %s block(s) changed",
                    result.get("name"), len(result.get("changed") or []))
        return result.get("id")
    logger.warning("startup profile refused: %s", result.get("error"))
    return None
