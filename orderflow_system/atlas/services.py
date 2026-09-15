"""Shared wiring for the hub's side channels — durable history + Telegram.

The engine attaches these when it starts the atlas layer; the REST layer attaches
them to a hub that has no engine behind it (replay-only use). One place, so both
paths behave identically.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def attach_services(
    hub: Any,
    atlas_cfg: Optional[dict[str, Any]] = None,
    telegram_cfg: Optional[dict[str, Any]] = None,
    db_path: Optional[str] = None,
    notify_cfg: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Attach an EventHistory and the notifier hub to *hub* (only if missing).

    The notifier is a ``NotifierHub`` holding every channel that has credentials
    (Telegram, ntfy, email). With none configured the hub is empty and alerts
    stay in the UI — which is exactly what a fresh install should do.
    """
    atlas_cfg = atlas_cfg or {}
    telegram_cfg = telegram_cfg or {}
    notify_cfg = notify_cfg or {}
    info: dict[str, Any] = {"history": False, "notifier": False, "channels": []}

    if getattr(hub, "history", None) is None:
        from orderflow_system.atlas.history import EventHistory

        enabled = bool((atlas_cfg.get("history") or {}).get("enabled", True))
        if db_path is None:
            try:
                from orderflow_system.desktop import config_store
                db_path = str(config_store.db_path())
            except Exception:                        # pragma: no cover - fallback
                db_path = "orderflow_data.db"
        hub.attach_history(EventHistory(str(db_path), enabled=enabled))
        info["history"] = True

    if getattr(hub, "notifier", None) is None:
        from orderflow_system.atlas.notify import build_notifiers

        atlas_tg = atlas_cfg.get("telegram") or {}
        notifier = build_notifiers(
            telegram_cfg=telegram_cfg,
            notify_cfg=notify_cfg,
            telegram_enabled=bool(atlas_tg.get("enabled", True)),
        )
        hub.attach_notifier(notifier)
        info["notifier"] = True
        info["channels"] = sorted(notifier.channels)

    return info
